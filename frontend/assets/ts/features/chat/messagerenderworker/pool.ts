/* SoAI - Main-thread WebWorker pool for chat message rendering [frontend/assets/ts/features/chat/messagerenderworker/pool.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { generateSecureId } from '@core/primitives/idGenerator.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError } from '@core/errors/abort.ts';
import type { RenderAssistantBodyFromMessageInput, RenderContext, RenderInlineDetailsFromMessageInput, RenderMessageCommonFields, WorkerRequest, WorkerResources } from '@features/chat/messagerenderworker/protocol.ts';
import { ChatRenderWorkerRequestQueue } from '@features/chat/messagerenderworker/workerRequestQueue.ts';
import { computeWorkerCount, isWorkerReadyMessage, isWorkerResponse, requireModernWorkerSupport } from '@features/chat/messagerenderworker/workerPoolEnvironment.ts';
import { minutesToMs, secondsToMs } from '@core/time/durations.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';

const CHAT_RENDER_WORKER_REQUEST_TIMEOUT_MS = secondsToMs(30);
const CHAT_RENDER_WORKER_BOOTSTRAP_TIMEOUT_MS = minutesToMs(2);

type WorkerBootstrap = Deferred<void> & {
    instanceId: string;
    ready: boolean;
    timeout: TimeoutTimer;
};

const createRenderMessageCommonFields = (inputArguments: RenderAssistantBodyFromMessageInput | RenderInlineDetailsFromMessageInput): RenderMessageCommonFields => {
    return {
        context: inputArguments.context,
        isRichTextEnabled: inputArguments.isRichTextEnabled,
        codeRecognitionEnabled: inputArguments.codeRecognitionEnabled,
        isThinkingFeatureEnabled: inputArguments.isThinkingFeatureEnabled,
        isShowActivitiesEnabled: inputArguments.isShowActivitiesEnabled,
        activityDurationDisplayMode: inputArguments.activityDurationDisplayMode,
        isCurrentConversationExecuting: inputArguments.isCurrentConversationExecuting,
        canonicalPlan: inputArguments.canonicalPlan,
        nowMs: inputArguments.nowMs,
        message: inputArguments.message
    };
};

class ChatMessageRenderWorkerPool {
    readonly #workers: Worker[];
    readonly #workerInstanceIds: string[];
    readonly #workerBootstraps: Array<WorkerBootstrap | undefined>;
    readonly #requestQueue: ChatRenderWorkerRequestQueue;
    #resources: WorkerResources;
    #resourcesReady: Promise<void>;

    constructor(resources: WorkerResources) {
        requireModernWorkerSupport();
        const count = computeWorkerCount();
        this.#workers = [];
        this.#workerInstanceIds = [];
        this.#workerBootstraps = [];
        this.#resources = resources;
        this.#resourcesReady = Promise.resolve();
        this.#requestQueue = new ChatRenderWorkerRequestQueue({
            dependencies: {
                workerCount: count,
                requestTimeoutMs: CHAT_RENDER_WORKER_REQUEST_TIMEOUT_MS,
                postToWorker: (workerIndex: number, payload: WorkerRequest): void => {
                    const worker = this.#workers[workerIndex];
                    if (!worker) {
                        throw new Error('Chat render worker selection failed');
                    }
                    worker.postMessage(payload);
                },
                recoverWorker: (workerIndex: number, error: Error): void => this.#replaceWorker(workerIndex, error)
            }
        });

        this.#resourcesReady = this.#initializeWorkerFleet(resources);
        this.#observeReadinessFailure('Worker fleet initialization failed');
    }

    getWorkerCount(): number {
        return this.#requestQueue.getWorkerCount();
    }

    dispose(): void {
        this.#requestQueue.rejectAll(new Error('Chat render worker pool disposed'));
        for (const [index, worker] of this.#workers.entries()) {
            this.#rejectWorkerBootstrap(index, new Error('Chat render worker pool disposed'));
            this.#workerInstanceIds[index] = generateSecureId();
            worker.terminate();
        }
        this.#workers.length = 0;
        this.#workerInstanceIds.length = 0;
        this.#workerBootstraps.length = 0;
    }

    updateResources(resources: WorkerResources): void {
        if (this.#workers.length === 0) {
            throw new Error('Chat render worker pool has no workers');
        }
        this.#resources = resources;
        this.#requestQueue.rejectAll(new Error('Chat render worker resources updated'));
        for (let index = 0; index < this.#workers.length; index += 1) {
            this.#rejectWorkerBootstrap(index, new Error('Chat render worker resources updated'));
            this.#workerInstanceIds[index] = generateSecureId();
            this.#workers[index]?.terminate();
        }
        this.#workers.length = 0;
        this.#workerInstanceIds.length = 0;
        this.#workerBootstraps.length = 0;
        this.#resourcesReady = this.#initializeWorkerFleet(resources);
        this.#observeReadinessFailure('Worker resource update failed');
    }

    #observeReadinessFailure(context: string): void {
        void this.#resourcesReady.catch((error) => {
            errorHandler.debug('ChatRenderWorkerPool', context, ensureError(error));
        });
    }

    renderAssistantBodyFromMessage(inputArguments: RenderAssistantBodyFromMessageInput): Promise<{ html: string; context: RenderContext }> {
        const signal = inputArguments.signal ?? null;
        const payload: WorkerRequest = {
            type: 'renderAssistantBodyFromMessage',
            requestId: generateSecureId(),
            ...createRenderMessageCommonFields(inputArguments),
            suppressAssistantActivityWidgets: inputArguments.suppressAssistantActivityWidgets
        };
        return this.#submitRenderRequest(payload, inputArguments.context, signal);
    }

    renderInlineDetailsFromMessage(inputArguments: RenderInlineDetailsFromMessageInput): Promise<{ html: string; context: RenderContext }> {
        const signal = inputArguments.signal ?? null;
        const payload: WorkerRequest = {
            type: 'renderInlineDetailsFromMessage',
            requestId: generateSecureId(),
            ...createRenderMessageCommonFields(inputArguments),
            expectedType: inputArguments.expectedType,
            callId: inputArguments.callId,
            timelineSequenceIndex: inputArguments.timelineSequenceIndex
        };
        return this.#submitRenderRequest(payload, inputArguments.context, signal);
    }

    #submitRenderRequest(payload: WorkerRequest, context: RenderContext, signal: AbortSignal | null): Promise<{ html: string; context: RenderContext }> {
        if (signal?.aborted) {
            return Promise.reject(createAbortError('Chat render worker request aborted'));
        }
        return this.#resourcesReady.then(() =>
            this.#requestQueue.enqueue({ payload, signal }).then((html) => {
                return { html, context };
            })
        );
    }

    #createWorker(workerIndex: number): Worker {
        const instanceId = generateSecureId();
        this.#workerInstanceIds[workerIndex] = instanceId;
        const worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module', name: `soai-chat-render-${workerIndex}` });
        const bootstrap = createDeferred<void>();
        const bootstrapTimeout = new TimeoutTimer(CHAT_RENDER_WORKER_BOOTSTRAP_TIMEOUT_MS, () => {
            if (this.#workerInstanceIds[workerIndex] === instanceId) {
                this.#failWorkerBootstrap(workerIndex, new Error('Chat render worker bootstrap timed out'));
            }
        });
        this.#workerBootstraps[workerIndex] = {
            ...bootstrap,
            instanceId,
            ready: false,
            timeout: bootstrapTimeout
        };
        worker.onmessage = (event: MessageEvent): void => {
            if (this.#workerInstanceIds[workerIndex] !== instanceId) {
                return;
            }
            if (isWorkerReadyMessage(event.data)) {
                this.#resolveWorkerBootstrap(workerIndex, instanceId);
                return;
            }
            this.#handleWorkerMessage(workerIndex, event.data);
        };
        worker.onerror = (event: ErrorEvent): void => {
            if (this.#workerInstanceIds[workerIndex] !== instanceId) {
                return;
            }
            const error = this.#buildWorkerCrashError(event);
            if (this.#workerBootstraps[workerIndex]?.ready === true) {
                this.#replaceWorker(workerIndex, error);
            } else {
                this.#failWorkerBootstrap(workerIndex, error);
            }
        };
        bootstrapTimeout.start();
        return worker;
    }

    #replaceWorker(workerIndex: number, error: Error): void {
        const crashedWorker = this.#workers[workerIndex];
        if (!crashedWorker) {
            return;
        }
        this.#rejectWorkerBootstrap(workerIndex, error);
        this.#requestQueue.rejectWorker(workerIndex, error);
        this.#workerInstanceIds[workerIndex] = generateSecureId();
        crashedWorker.terminate();
        this.#workers[workerIndex] = this.#createWorker(workerIndex);
        const replacementInstanceId = this.#workerInstanceIds[workerIndex];
        const recovery = this.#initializeWorkerResources(workerIndex, this.#resources).catch((error) => {
            const runtimeError = ensureError(error);
            if (this.#workerInstanceIds[workerIndex] === replacementInstanceId) {
                this.#requestQueue.rejectWorker(workerIndex, runtimeError);
            }
            throw runtimeError;
        });
        const previousResourcesReady = this.#resourcesReady.catch((error) => {
            errorHandler.debug('ChatRenderWorkerPool', 'Previous worker resource initialization failed before replacement recovery', ensureError(error));
            return undefined;
        });
        this.#resourcesReady = Promise.all([previousResourcesReady, recovery]).then(() => this.#initializeWorkerFleet(this.#resources));
        this.#observeReadinessFailure('Worker replacement failed');
    }

    #failWorkerBootstrap(workerIndex: number, error: Error): void {
        const worker = this.#workers[workerIndex];
        if (!worker) {
            return;
        }
        this.#rejectWorkerBootstrap(workerIndex, error);
        this.#requestQueue.rejectWorker(workerIndex, error);
        this.#workerInstanceIds[workerIndex] = generateSecureId();
        worker.terminate();
    }

    #buildWorkerCrashError(event: ErrorEvent): Error {
        const details: string[] = [];
        if (event.message) {
            details.push(event.message);
        }
        if (event.filename) {
            const location = event.lineno || event.colno ? `${event.filename}:${event.lineno}:${event.colno}` : event.filename;
            details.push(location);
        }
        const message = details.length ? `Chat render worker crashed: ${details.join(' | ')}` : 'Chat render worker crashed';
        return new Error(message);
    }

    #handleWorkerMessage(workerIndex: number, value: JsonValue | null | undefined): void {
        if (!isWorkerResponse(value)) {
            this.#replaceWorker(workerIndex, new Error('Chat render worker returned an invalid response'));
            return;
        }
        this.#requestQueue.handleWorkerResponse(workerIndex, value);
    }

    #resolveWorkerBootstrap(workerIndex: number, instanceId: string): void {
        const bootstrap = this.#workerBootstraps[workerIndex];
        if (!bootstrap || bootstrap.instanceId !== instanceId) {
            return;
        }
        bootstrap.timeout.stop();
        bootstrap.ready = true;
        bootstrap.resolve();
    }

    #rejectWorkerBootstrap(workerIndex: number, error: Error): void {
        const bootstrap = this.#workerBootstraps[workerIndex];
        if (!bootstrap) {
            return;
        }
        this.#workerBootstraps[workerIndex] = undefined;
        bootstrap.timeout.stop();
        bootstrap.reject(error);
    }

    async #initializeWorkerFleet(resources: WorkerResources): Promise<void> {
        const workerCount = this.#requestQueue.getWorkerCount();
        const createdWorkerIndexes: number[] = [];
        for (let index = 0; index < workerCount; index += 1) {
            if (this.#workers[index]) {
                continue;
            }
            this.#workers[index] = this.#createWorker(index);
            createdWorkerIndexes.push(index);
        }
        await Promise.all(createdWorkerIndexes.map(async (workerIndex) => await this.#initializeWorkerResources(workerIndex, resources)));
    }

    async #initializeWorkerResources(workerIndex: number, resources: WorkerResources): Promise<void> {
        const bootstrap = this.#workerBootstraps[workerIndex];
        if (!bootstrap || bootstrap.instanceId !== this.#workerInstanceIds[workerIndex]) {
            throw new Error('Chat render worker bootstrap state is unavailable');
        }
        await bootstrap.promise;
        const requestId = generateSecureId();
        const payload: WorkerRequest = { type: 'initResources', requestId, resources };
        await this.#requestQueue.dispatchToWorker({ workerIndex, payload, signal: null });
    }
}

export { ChatMessageRenderWorkerPool };
