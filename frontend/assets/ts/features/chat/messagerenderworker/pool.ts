/* SoAI - Main-thread WebWorker pool for chat message rendering [frontend/assets/ts/features/chat/messagerenderworker/pool.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import ChatRenderWorker from '@features/chat/messagerenderworker/worker.ts?worker&inline';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError } from '@core/errors/abort.ts';
import type { RenderAssistantBodyFromMessageInput, RenderContext, RenderInlineDetailsFromMessageInput, RenderMessageCommonFields, WorkerMessage, WorkerRequest, WorkerResources } from '@features/chat/messagerenderworker/protocol.ts';
import { ChatRenderWorkerRequestQueue } from '@features/chat/messagerenderworker/workerRequestQueue.ts';
import { computeWorkerCount, isWorkerReadyMessage, isWorkerResponse, requireModernWorkerSupport } from '@features/chat/messagerenderworker/workerPoolEnvironment.ts';
import { minutesToMs, secondsToMs } from '@core/time/durations.ts';
import { WorkerSession } from '@core/runtime/WorkerSession.ts';

const CHAT_RENDER_WORKER_REQUEST_TIMEOUT_MS = secondsToMs(30);
const CHAT_RENDER_WORKER_BOOTSTRAP_TIMEOUT_MS = minutesToMs(2);

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
    readonly #workers: Array<WorkerSession<WorkerRequest, WorkerMessage> | undefined>;
    readonly #workerInstanceIds: string[];
    readonly #requestQueue: ChatRenderWorkerRequestQueue;
    #resources: WorkerResources;
    #resourcesReady: Promise<void>;

    constructor(resources: WorkerResources) {
        requireModernWorkerSupport();
        const count = computeWorkerCount();
        this.#workers = [];
        this.#workerInstanceIds = [];
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

    dispose(error: Error = new Error('Chat render worker pool disposed')): void {
        this.#requestQueue.rejectAll(error);
        for (const [index, worker] of this.#workers.entries()) {
            this.#workerInstanceIds[index] = generateSecureId();
            worker?.dispose(error);
        }
        this.#workers.length = 0;
        this.#workerInstanceIds.length = 0;
    }

    updateResources(resources: WorkerResources): void {
        if (this.#workers.length === 0) {
            throw new Error('Chat render worker pool has no workers');
        }
        this.#resources = resources;
        this.#requestQueue.rejectAll(new Error('Chat render worker resources updated'));
        for (let index = 0; index < this.#workers.length; index += 1) {
            this.#workerInstanceIds[index] = generateSecureId();
            this.#workers[index]?.dispose(new Error('Chat render worker resources updated'));
        }
        this.#workers.length = 0;
        this.#workerInstanceIds.length = 0;
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

    #createWorker(workerIndex: number): WorkerSession<WorkerRequest, WorkerMessage> {
        const instanceId = generateSecureId();
        this.#workerInstanceIds[workerIndex] = instanceId;
        return new WorkerSession({
            createWorker: () => new ChatRenderWorker({ name: `soai-chat-render-${workerIndex}` }),
            label: 'Chat render worker',
            timeoutMs: CHAT_RENDER_WORKER_BOOTSTRAP_TIMEOUT_MS,
            decode: (value) => {
                if (isWorkerReadyMessage(value) || isWorkerResponse(value)) return value;
                throw new Error('Chat render worker returned an invalid response');
            },
            isReady: isWorkerReadyMessage,
            onMessage: (response) => {
                if (this.#workerInstanceIds[workerIndex] === instanceId && isWorkerResponse(response)) this.#requestQueue.handleWorkerResponse(workerIndex, response);
            },
            onFailure: (error, wasReady) => {
                if (this.#workerInstanceIds[workerIndex] !== instanceId) return;
                if (wasReady) this.#replaceWorker(workerIndex, error);
                else this.#requestQueue.rejectWorker(workerIndex, error);
            }
        });
    }

    #replaceWorker(workerIndex: number, error: Error): void {
        const crashedWorker = this.#workers[workerIndex];
        if (!crashedWorker) {
            return;
        }
        this.#requestQueue.rejectWorker(workerIndex, error);
        this.#workerInstanceIds[workerIndex] = generateSecureId();
        crashedWorker.dispose(error);
        try {
            this.#workers[workerIndex] = this.#createWorker(workerIndex);
        } catch (error) {
            const failure = ensureError(error);
            this.dispose(failure);
            this.#resourcesReady = Promise.reject(failure);
            void this.#resourcesReady.catch((error) => {
                errorHandler.debug('ChatRenderWorkerPool', 'Worker replacement construction failed', ensureError(error));
            });
            return;
        }
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
        this.#resourcesReady = Promise.all([previousResourcesReady, recovery]).then(() => {
            if (this.#workerInstanceIds[workerIndex] !== replacementInstanceId) throw createAbortError('Chat render worker recovery was superseded');
            return this.#initializeWorkerFleet(this.#resources);
        });
        this.#observeReadinessFailure('Worker replacement failed');
    }

    async #initializeWorkerFleet(resources: WorkerResources): Promise<void> {
        const workerCount = this.#requestQueue.getWorkerCount();
        const createdWorkers: Array<{ index: number; worker: WorkerSession<WorkerRequest, WorkerMessage> }> = [];
        const startups: Promise<void>[] = [];
        try {
            for (let index = 0; index < workerCount; index += 1) {
                if (this.#workers[index]) continue;
                const worker = this.#createWorker(index);
                this.#workers[index] = worker;
                createdWorkers.push({ index, worker });
                startups.push(this.#initializeWorkerResources(index, resources));
            }
            await Promise.all(startups);
        } catch (error) {
            const failure = ensureError(error);
            for (const { index, worker } of createdWorkers) {
                worker.dispose(failure);
                if (this.#workers[index] === worker) {
                    this.#workers[index] = undefined;
                    this.#workerInstanceIds[index] = generateSecureId();
                    this.#requestQueue.rejectWorker(index, failure);
                }
            }
            await Promise.allSettled(startups);
            throw failure;
        }
    }

    async #initializeWorkerResources(workerIndex: number, resources: WorkerResources): Promise<void> {
        const worker = this.#workers[workerIndex];
        if (!worker) throw new Error('Chat render worker bootstrap state is unavailable');
        await worker.ready;
        if (this.#workers[workerIndex] !== worker) throw new Error('Chat render worker initialization was superseded');
        const requestId = generateSecureId();
        const payload: WorkerRequest = { type: 'initResources', requestId, resources };
        await this.#requestQueue.dispatchToWorker({ workerIndex, payload, signal: null });
    }
}

export { ChatMessageRenderWorkerPool };
