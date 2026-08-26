/* SoAI - Request scheduling/cancellation for chat render worker pools [frontend/assets/ts/features/chat/messagerenderworker/workerRequestQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WorkerRequest, WorkerResponse } from '@features/chat/messagerenderworker/protocol.ts';
import { registerAbortListener } from '@features/chat/abort/abortSignalListener.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import type { ChatRenderWorkerRequestQueueDependencies, PendingRequest, QueuedRequest } from '@features/chat/messagerenderworker/workerRequestQueueTypes.ts';

class ChatRenderWorkerRequestQueue {
    readonly #dependencies: ChatRenderWorkerRequestQueueDependencies;
    readonly #pending: Map<string, PendingRequest>;
    readonly #queue: Map<string, QueuedRequest>;
    readonly #workerBusy: boolean[];
    #nextIndex: number;

    constructor(inputArguments: { dependencies: ChatRenderWorkerRequestQueueDependencies }) {
        this.#dependencies = inputArguments.dependencies;
        if (!Number.isInteger(this.#dependencies.workerCount) || this.#dependencies.workerCount <= 0) {
            throw new Error('Chat render worker queue requires a positive worker count');
        }
        if (!Number.isFinite(this.#dependencies.requestTimeoutMs) || this.#dependencies.requestTimeoutMs <= 0) {
            throw new Error('Chat render worker queue requires a positive request timeout');
        }
        this.#pending = new Map();
        this.#queue = new Map();
        this.#workerBusy = Array.from({ length: this.#dependencies.workerCount }, () => false);
        this.#nextIndex = 0;
    }

    getWorkerCount(): number {
        return this.#dependencies.workerCount;
    }

    #resolveRequestAdmission(payload: WorkerRequest, signal: AbortSignal | null): { requestId: string; alreadyAborted: boolean } {
        const requestId = payload.requestId;
        if (!requestId) {
            throw new Error('Chat render worker request requires requestId');
        }
        if (this.#pending.has(requestId) || this.#queue.has(requestId)) {
            throw new Error('Chat render worker requestId collision');
        }
        return { requestId, alreadyAborted: signal?.aborted === true };
    }

    enqueue(inputArguments: { payload: WorkerRequest; signal: AbortSignal | null }): Promise<string> {
        if (this.#queue.size >= 2000) {
            throw new Error('Chat render worker queue overflow');
        }
        const admission = this.#resolveRequestAdmission(inputArguments.payload, inputArguments.signal);
        if (admission.alreadyAborted) {
            return Promise.reject(createAbortError('Chat render worker request aborted'));
        }
        const requestId = admission.requestId;
        const deferred = createDeferred<string>();
        const entry: QueuedRequest = {
            requestId,
            payload: inputArguments.payload,
            resolve: (html): void => deferred.resolve(html),
            reject: (error): void => deferred.reject(error),
            signal: inputArguments.signal,
            abortDisposer: null
        };
        this.#queue.set(requestId, entry);
        if (inputArguments.signal) {
            entry.abortDisposer = registerAbortListener(inputArguments.signal, (): void => {
                this.cancelRequest(requestId);
            });
        }
        this.#pumpQueue();
        return deferred.promise;
    }

    dispatchToWorker(inputArguments: { workerIndex: number; payload: WorkerRequest; signal: AbortSignal | null }): Promise<string> {
        if (!Number.isInteger(inputArguments.workerIndex) || inputArguments.workerIndex < 0 || inputArguments.workerIndex >= this.#dependencies.workerCount) {
            throw new Error('Chat render worker queue invalid workerIndex');
        }
        const admission = this.#resolveRequestAdmission(inputArguments.payload, inputArguments.signal);
        if (admission.alreadyAborted) {
            return Promise.reject(createAbortError('Chat render worker request aborted'));
        }
        const requestId = admission.requestId;
        const deferred = createDeferred<string>();
        this.#workerBusy[inputArguments.workerIndex] = true;
        const pending: PendingRequest = {
            workerIndex: inputArguments.workerIndex,
            resolve: (html: string): void => deferred.resolve(html),
            reject: (error: Error): void => deferred.reject(error),
            abortDisposer: null,
            deadlineTimer: null,
            cancelled: false
        };
        this.#pending.set(requestId, pending);
        if (inputArguments.signal) {
            pending.abortDisposer = registerAbortListener(inputArguments.signal, () => this.cancelRequest(requestId));
        }
        this.#armDeadline(requestId, pending);
        this.#postOrRecover(inputArguments.workerIndex, requestId, inputArguments.payload);
        return deferred.promise;
    }

    #clearPendingLifecycle(pending: PendingRequest): void {
        pending.abortDisposer?.();
        pending.abortDisposer = null;
        pending.deadlineTimer?.stop();
        pending.deadlineTimer = null;
    }

    cancelRequest(requestId: string): void {
        if (!requestId) {
            return;
        }
        const pending = this.#pending.get(requestId) ?? null;
        if (pending) {
            if (pending.cancelled) {
                return;
            }
            pending.cancelled = true;
            pending.abortDisposer?.();
            pending.abortDisposer = null;
            pending.reject(createAbortError('Chat render worker request aborted'));
            return;
        }
        const queued = this.#queue.get(requestId) ?? null;
        if (queued) {
            this.#queue.delete(requestId);
            queued.abortDisposer?.();
            queued.abortDisposer = null;
            queued.reject(createAbortError('Chat render worker request aborted'));
        }
    }

    handleWorkerResponse(workerIndex: number, response: WorkerResponse): void {
        const pending = this.#pending.get(response.requestId) ?? null;
        if (!pending) {
            this.#dependencies.recoverWorker(workerIndex, new Error('Chat render worker returned an uncorrelated response'));
            return;
        }
        if (pending.workerIndex !== workerIndex) {
            this.#dependencies.recoverWorker(workerIndex, new Error('Chat render worker response routing mismatch'));
            return;
        }
        this.#pending.delete(response.requestId);
        this.#clearPendingLifecycle(pending);
        this.#workerBusy[workerIndex] = false;
        if (pending.cancelled) {
            this.#pumpQueue();
            return;
        }
        if (response.type === 'rendered') {
            pending.resolve(response.html);
            this.#pumpQueue();
            return;
        }
        if (response.type === 'ok') {
            pending.resolve('');
            this.#pumpQueue();
            return;
        }
        pending.reject(new Error(response.message));
        this.#pumpQueue();
    }

    rejectAll(error: Error): void {
        for (const pending of this.#pending.values()) {
            this.#clearPendingLifecycle(pending);
            if (!pending.cancelled) pending.reject(error);
        }
        this.#pending.clear();
        for (const queued of this.#queue.values()) {
            if (queued.abortDisposer) {
                queued.abortDisposer();
                queued.abortDisposer = null;
            }
            queued.reject(error);
        }
        this.#queue.clear();
        for (let index = 0; index < this.#workerBusy.length; index += 1) {
            this.#workerBusy[index] = false;
        }
    }

    rejectWorker(workerIndex: number, error: Error): void {
        if (!Number.isInteger(workerIndex) || workerIndex < 0 || workerIndex >= this.#workerBusy.length) {
            return;
        }
        for (const [requestId, pending] of this.#pending.entries()) {
            if (pending.workerIndex !== workerIndex) {
                continue;
            }
            this.#clearPendingLifecycle(pending);
            if (!pending.cancelled) pending.reject(error);
            this.#pending.delete(requestId);
        }
        this.#workerBusy[workerIndex] = true;
    }

    #pumpQueue(): void {
        while (this.#queue.size > 0) {
            const workerIndex = this.#selectIdleWorkerIndex();
            if (workerIndex === null) {
                return;
            }
            let next: QueuedRequest | null = null;
            for (const queued of this.#queue.values()) {
                next = queued;
                break;
            }
            if (next === null) {
                return;
            }
            this.#queue.delete(next.requestId);
            this.#workerBusy[workerIndex] = true;
            const pending: PendingRequest = { workerIndex, resolve: next.resolve, reject: next.reject, abortDisposer: next.abortDisposer, deadlineTimer: null, cancelled: false };
            this.#pending.set(next.requestId, pending);
            next.abortDisposer = null;
            this.#armDeadline(next.requestId, pending);
            this.#postOrRecover(workerIndex, next.requestId, next.payload);
        }
    }

    #armDeadline(requestId: string, pending: PendingRequest): void {
        pending.deadlineTimer = new TimeoutTimer(this.#dependencies.requestTimeoutMs, () => {
            const error = new Error('Chat render worker request timed out');
            this.#pending.delete(requestId);
            this.#clearPendingLifecycle(pending);
            if (!pending.cancelled) pending.reject(error);
            this.#dependencies.recoverWorker(pending.workerIndex, error);
        });
        pending.deadlineTimer.start();
    }

    #postOrRecover(workerIndex: number, requestId: string, payload: WorkerRequest): void {
        try {
            this.#dependencies.postToWorker(workerIndex, payload);
        } catch (error) {
            const pending = this.#pending.get(requestId) ?? null;
            if (!pending) {
                return;
            }
            const runtimeError = ensureError(error);
            this.#pending.delete(requestId);
            this.#clearPendingLifecycle(pending);
            pending.reject(runtimeError);
            this.#dependencies.recoverWorker(workerIndex, runtimeError);
        }
    }

    #selectIdleWorkerIndex(): number | null {
        for (let attempt = 0; attempt < this.#workerBusy.length; attempt += 1) {
            const index = this.#nextIndex % this.#workerBusy.length;
            this.#nextIndex += 1;
            if (this.#workerBusy[index] !== true) {
                return index;
            }
        }
        return null;
    }
}

export { ChatRenderWorkerRequestQueue };
