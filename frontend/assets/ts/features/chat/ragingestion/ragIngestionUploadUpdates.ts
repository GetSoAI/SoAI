/* SoAI - Chat feature RAG ingestion upload updates [frontend/assets/ts/features/chat/ragingestion/ragIngestionUploadUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { i18n } from '@core/i18n/index.ts';
import type { RagIngestionStatus } from '@features/chat/public.ts';
import type { RagBatchUploadOutcome } from '@features/chat/ragingestion/ragIngestionBatchResults.ts';
import { selectLatestKnowledgeAttachmentSummary } from '@features/chat/knowledgeAttachmentPresentation.ts';

type RagIngestionBackoffState = {
    pausedUntilMs: number;
    rateLimitBackoffMs: number;
};

type RagIngestionUploadUpdateResult = {
    nextStatus: RagIngestionStatus;
    filesToRequeue: readonly File[];
    nextBackoff: RagIngestionBackoffState;
};

const applyBatchUploadOutcomeToIngestionState = (inputArguments: { status: RagIngestionStatus; outcome: RagBatchUploadOutcome; backoff: RagIngestionBackoffState; nowMs: number }): RagIngestionUploadUpdateResult => {
    const { status, outcome, backoff, nowMs } = inputArguments;
    if (outcome.rateLimitedCount <= 0) {
        return {
            nextStatus: {
                ...status,
                succeeded: status.succeeded + outcome.succeededCount,
                failed: status.failed + outcome.failedCount,
                lastError: outcome.failedCount > 0 ? i18n.t('chat.ingestion.failed') : null,
                knowledgeAttachment: outcome.knowledgeAttachment ?? status.knowledgeAttachment
            },
            filesToRequeue: [],
            nextBackoff: { pausedUntilMs: backoff.pausedUntilMs, rateLimitBackoffMs: 5000 }
        };
    }

    const retryAfterMs = outcome.maxRetryAfterSeconds > 0 ? outcome.maxRetryAfterSeconds * 1000 : 0;
    const pauseMs = Math.max(retryAfterMs, backoff.rateLimitBackoffMs);
    return {
        nextStatus: {
            ...status,
            succeeded: status.succeeded + outcome.succeededCount,
            failed: status.failed + outcome.failedCount,
            lastError: i18n.t('chat.ingestion.backpressure'),
            knowledgeAttachment: outcome.knowledgeAttachment ?? status.knowledgeAttachment
        },
        filesToRequeue: outcome.rateLimitedFiles,
        nextBackoff: { pausedUntilMs: nowMs + pauseMs, rateLimitBackoffMs: Math.min(30000, backoff.rateLimitBackoffMs * 2) }
    };
};

const applyUploadErrorToIngestionState = (inputArguments: { status: RagIngestionStatus; files: readonly File[]; error: Error; backoff: RagIngestionBackoffState; nowMs: number }): RagIngestionUploadUpdateResult => {
    const { status, files, error, backoff, nowMs } = inputArguments;
    if (error instanceof APIError && error.status === 429) {
        return {
            nextStatus: { ...status, lastError: i18n.t('chat.ingestion.backpressure') },
            filesToRequeue: files,
            nextBackoff: { pausedUntilMs: nowMs + backoff.rateLimitBackoffMs, rateLimitBackoffMs: Math.min(30000, backoff.rateLimitBackoffMs * 2) }
        };
    }
    return {
        nextStatus: { ...status, failed: status.failed + files.length, lastError: i18n.t('chat.ingestion.failed') },
        filesToRequeue: [],
        nextBackoff: { pausedUntilMs: backoff.pausedUntilMs, rateLimitBackoffMs: backoff.rateLimitBackoffMs }
    };
};

const mergeRagIngestionUploadUpdate = (current: RagIngestionStatus, baseline: RagIngestionStatus, nextStatus: RagIngestionStatus): RagIngestionStatus => {
    const succeededDelta = Math.max(0, nextStatus.succeeded - baseline.succeeded);
    const failedDelta = Math.max(0, nextStatus.failed - baseline.failed);
    return {
        ...current,
        succeeded: current.succeeded + succeededDelta,
        failed: current.failed + failedDelta,
        lastError: nextStatus.lastError ?? (current.failed > 0 || failedDelta > 0 ? current.lastError : null),
        knowledgeAttachment: nextStatus.knowledgeAttachment === null ? current.knowledgeAttachment : current.knowledgeAttachment === null ? nextStatus.knowledgeAttachment : selectLatestKnowledgeAttachmentSummary(current.knowledgeAttachment, nextStatus.knowledgeAttachment)
    };
};

export { applyBatchUploadOutcomeToIngestionState, applyUploadErrorToIngestionState, mergeRagIngestionUploadUpdate };
export type { RagIngestionBackoffState, RagIngestionUploadUpdateResult };
