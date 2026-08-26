/* SoAI - Chat feature RAG ingestion controller [frontend/assets/ts/features/chat/ragingestion/RagIngestionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { normalizeConversationId, type RagIngestionAttachmentSource, type RagIngestionStatus } from '@features/chat/public.ts';
import type { RagIngestionBatchStateUpdate } from '@features/chat/ragingestion/batchupload/state.ts';
import { cancelRagIngestionFlow } from '@features/chat/ragingestion/cancellation/service.ts';
import { resolveCompletedRagIngestionStatus } from '@features/chat/ragingestion/finalization/state.ts';
import { uploadRagIngestionBatch } from '@features/chat/ragingestion/service.ts';
import type { RagIngestionControllerDependencies, RagQueuedIngestionFile, StartIngestionArguments } from '@features/chat/ragingestion/contracts.ts';
import { RagIngestionPauseController } from '@features/chat/ragingestion/RagIngestionPauseController.ts';
import { RagIngestionQueuePacer } from '@features/chat/ragingestion/queue/service.ts';
import { RagIngestionUploadLifecycleManager } from '@features/chat/ragingestion/ragIngestionUploadLifecycleManager.ts';
import { RagIngestionUploadIdentityManager } from '@features/chat/ragingestion/RagIngestionUploadIdentityManager.ts';
import { buildValidatedIngestionQueue, initializeStatusForIngestionStart, validateRagIngestionStartRequest } from '@features/chat/ragingestion/ragIngestionStart.ts';
import { mergeRagIngestionUploadUpdate } from '@features/chat/ragingestion/ragIngestionUploadUpdates.ts';

class RagIngestionController {
    #dependencies: RagIngestionControllerDependencies;
    #status: RagIngestionStatus | null = null;
    #queue: RagQueuedIngestionFile[] = [];
    #inFlight = 0;
    #concurrency = 2;
    #batchSize = 10;
    #cancelRequested = false;
    #pausedUntilMs = 0;
    #rateLimitBackoffMs = 5000;
    #disposed = false;
    #uploadIdentity = new RagIngestionUploadIdentityManager();
    #uploadLifecycle = new RagIngestionUploadLifecycleManager();
    #pauseController: RagIngestionPauseController;
    #queuePacer: RagIngestionQueuePacer;

    constructor(dependencies: RagIngestionControllerDependencies) {
        this.#dependencies = dependencies;
        this.#queuePacer = new RagIngestionQueuePacer(dependencies.listDocuments);
        this.#pauseController = new RagIngestionPauseController({
            getPausedUntilMs: () => this.#pausedUntilMs,
            isStopped: () => this.#disposed || this.#cancelRequested,
            resume: () => this.#pump(),
            warn: (message, error) => errorHandler.warn('RagIngestionController', message, error)
        });
    }

    getStatusForConversation(conversationId: string): RagIngestionStatus | null {
        if (this.#disposed) {
            return null;
        }
        const current = this.#status;
        if (!current) {
            return null;
        }
        const normalizedId = normalizeConversationId(conversationId);
        if (!normalizedId) {
            return null;
        }
        return current.conversationId === normalizedId ? current : null;
    }

    async cancel(conversationId: string): Promise<void> {
        if (this.#disposed) {
            return;
        }
        await cancelRagIngestionFlow({
            status: this.#status,
            conversationId,
            inFlight: this.#inFlight,
            getCurrentStatus: () => this.#status,
            isDisposed: () => this.#disposed,
            cancelKnowledgeAttachment: this.#dependencies.cancelKnowledgeAttachment,
            signal: this.#dependencies.resolveAbortSignal(),
            applyCancelledStatus: (status) => {
                this.#cancelRequested = true;
                this.#queue = [];
                this.#uploadLifecycle.abortActive();
                this.#status = status;
                this.#dependencies.onStatusChange(this.#status);
            }
        });
    }

    async start(inputArguments: StartIngestionArguments): Promise<void> {
        if (this.#disposed) {
            throw new Error('RAG ingestion controller has been disposed');
        }
        const request = validateRagIngestionStartRequest(inputArguments);
        if (request === null) {
            return;
        }
        const { conversationId, files, attachmentSource } = request;
        const validated = buildValidatedIngestionQueue(files);
        if (validated.queuedFiles.length === 0) {
            if (validated.lastError) {
                throw new Error(validated.lastError);
            }
            throw new Error('No valid files were selected for knowledge ingestion');
        }
        const existing = this.#status;
        if (existing && existing.state !== 'submitted' && existing.state !== 'cancelled' && existing.conversationId !== conversationId) {
            throw new Error('A knowledge ingestion job is already running for another conversation');
        }

        const initialize = initializeStatusForIngestionStart(existing, conversationId, files.length);
        this.#status = initialize.status;
        this.#cancelRequested = false;
        if (initialize.resetQueue) {
            this.#queue = [];
            this.#pausedUntilMs = 0;
            this.#rateLimitBackoffMs = 5000;
            this.#pauseController.reset();
            this.#queuePacer.reset();
        }
        if (initialize.resetInFlight) this.#inFlight = 0;
        if (initialize.resetInFlight) this.#uploadLifecycle.startGeneration();

        if (validated.skippedCount > 0 || validated.lastError) {
            this.#status = { ...this.#status, skipped: this.#status.skipped + validated.skippedCount, lastError: validated.lastError };
        }
        this.#queue.push(...validated.queuedFiles.map((file) => ({ file, attachmentSource })));
        const clientBatchId = this.#uploadIdentity.begin(initialize.resetQueue);
        this.#status = { ...this.#status, clientBatchId };

        this.#syncQueuedCount();
        this.#dependencies.onStatusChange(this.#status);
        this.#pump();
    }

    #syncQueuedCount(): void {
        if (!this.#status) {
            return;
        }
        this.#status = { ...this.#status, queued: this.#queue.length, inFlight: this.#inFlight };
    }

    #pump(): void {
        if (this.#disposed) {
            return;
        }
        const current = this.#status;
        if (!current) {
            return;
        }
        if (this.#cancelRequested) {
            return;
        }
        if (current.state === 'cancelled' || current.state === 'submitted') {
            return;
        }
        const now = monotonicMs();
        if (this.#pausedUntilMs > now) {
            if (current.state !== 'paused') {
                this.#status = { ...current, state: 'paused', queued: this.#queue.length, inFlight: this.#inFlight };
                this.#dependencies.onStatusChange(this.#status);
            }
            this.#pauseController.schedule();
            return;
        }
        if (current.state === 'paused') {
            this.#status = { ...current, state: 'running', queued: this.#queue.length, inFlight: this.#inFlight };
            this.#dependencies.onStatusChange(this.#status);
        }
        while (this.#inFlight < this.#concurrency && this.#queue.length > 0) {
            const firstEntry = this.#queue.shift();
            if (firstEntry === undefined) {
                break;
            }
            const batch: File[] = [firstEntry.file];
            const attachmentSource = firstEntry.attachmentSource;
            while (batch.length < this.#batchSize && this.#queue.length > 0 && this.#queue[0]?.attachmentSource === attachmentSource) {
                const nextEntry = this.#queue.shift();
                if (nextEntry !== undefined) {
                    batch.push(nextEntry.file);
                }
            }
            this.#inFlight += 1;
            this.#syncQueuedCount();
            this.#dependencies.onStatusChange(this.#status);
            void this.#uploadBatch(batch, attachmentSource).catch((error) => {
                errorHandler.warn('RagIngestionController', 'Unhandled error while uploading ingestion item', ensureError(error));
            });
        }

        this.#syncQueuedCount();
        this.#dependencies.onStatusChange(this.#status);
        const completed = resolveCompletedRagIngestionStatus({
            status: this.#status,
            queuedCount: this.#queue.length,
            inFlightCount: this.#inFlight
        });
        if (completed !== null) {
            this.#status = completed;
            this.#dependencies.onStatusChange(this.#status);
        }
    }

    async #uploadBatch(files: File[], attachmentSource: RagIngestionAttachmentSource): Promise<void> {
        const status = this.#status;
        if (this.#disposed || !status) {
            this.#inFlight = Math.max(0, this.#inFlight - 1);
            return;
        }
        if (this.#cancelRequested) {
            this.#inFlight = Math.max(0, this.#inFlight - 1);
            this.#syncQueuedCount();
            this.#dependencies.onStatusChange(this.#status);
            return;
        }
        const uploadGeneration = this.#uploadLifecycle.generation;
        const uploadController = this.#uploadLifecycle.createController();
        const uploadIdentity = this.#uploadIdentity.requireSnapshot(attachmentSource);
        try {
            const update = await uploadRagIngestionBatch({
                status,
                files,
                queuePacer: this.#queuePacer,
                backoff: { pausedUntilMs: this.#pausedUntilMs, rateLimitBackoffMs: this.#rateLimitBackoffMs },
                isStopped: () => this.#disposed || this.#cancelRequested || this.#status?.state === 'cancelled',
                runWithBoundary: this.#dependencies.runWithBoundary,
                uploadDocumentsBatch: this.#dependencies.uploadDocumentsBatch,
                uploadOptions: { signal: uploadController.signal, query: { attachmentSource: uploadIdentity.attachmentSource, clientBatchId: uploadIdentity.clientBatchId } }
            });
            if (this.#disposed || this.#cancelRequested || this.#status?.state === 'cancelled') {
                return;
            }
            if (update) {
                this.#applyBatchStateUpdate(update, status, attachmentSource);
            }
        } finally {
            this.#uploadLifecycle.releaseController(uploadController);
            if (!this.#uploadLifecycle.isCurrent(uploadGeneration)) {
                return;
            }
            this.#inFlight = Math.max(0, this.#inFlight - 1);
            if (this.#disposed) {
                return;
            }
            this.#syncQueuedCount();
            this.#dependencies.onStatusChange(this.#status);
            this.#pump();
        }
    }

    #applyBatchStateUpdate(update: RagIngestionBatchStateUpdate, baseline: RagIngestionStatus, attachmentSource: RagIngestionAttachmentSource): void {
        if (update.filesToRequeue.length > 0) {
            this.#queue.unshift(...update.filesToRequeue.map((file) => ({ file, attachmentSource })));
        }
        this.#pausedUntilMs = update.nextBackoff.pausedUntilMs;
        this.#rateLimitBackoffMs = update.nextBackoff.rateLimitBackoffMs;
        if (this.#status !== null) {
            this.#status = mergeRagIngestionUploadUpdate(this.#status, baseline, update.nextStatus);
        }
    }

    dispose(): void {
        if (this.#disposed) {
            return;
        }
        this.#disposed = true;
        this.#cancelRequested = true;
        this.#uploadLifecycle.abortActive();
        this.#queue = [];
        this.#uploadIdentity.clear();
        this.#status = null;
        this.#inFlight = 0;
        this.#pausedUntilMs = 0;
        this.#pauseController.reset();
        this.#queuePacer.reset();
    }
}

export { RagIngestionController };
