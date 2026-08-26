/* SoAI - RAG ingestion batch upload state transitions [frontend/assets/ts/features/chat/ragingestion/batchupload/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { RagBatchUploadResponse } from '@core/api/contracts/webuiRagContracts.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { RagIngestionStatus } from '@features/chat/public.ts';
import { parseRagBatchUploadOutcome } from '@features/chat/ragingestion/ragIngestionBatchResults.ts';
import { applyBatchUploadOutcomeToIngestionState, applyUploadErrorToIngestionState } from '@features/chat/ragingestion/ragIngestionUploadUpdates.ts';

type RagIngestionBatchBackoff = {
    pausedUntilMs: number;
    rateLimitBackoffMs: number;
};

type RagIngestionBatchStateUpdate = {
    nextStatus: RagIngestionStatus;
    filesToRequeue: readonly File[];
    nextBackoff: RagIngestionBatchBackoff;
};

const applySuccessfulRagIngestionBatchUpload = (inputArguments: { status: RagIngestionStatus; files: File[]; payload: RagBatchUploadResponse; backoff: RagIngestionBatchBackoff }): RagIngestionBatchStateUpdate => {
    return applyBatchUploadOutcomeToIngestionState({
        status: inputArguments.status,
        outcome: parseRagBatchUploadOutcome(inputArguments.payload, inputArguments.files),
        nowMs: monotonicMs(),
        backoff: inputArguments.backoff
    });
};

const applyFailedRagIngestionBatchUpload = (inputArguments: { status: RagIngestionStatus; files: File[]; error: Error; backoff: RagIngestionBatchBackoff }): RagIngestionBatchStateUpdate => {
    return applyUploadErrorToIngestionState({
        status: inputArguments.status,
        files: inputArguments.files,
        error: ensureError(inputArguments.error),
        nowMs: monotonicMs(),
        backoff: inputArguments.backoff
    });
};

export { applyFailedRagIngestionBatchUpload, applySuccessfulRagIngestionBatchUpload };
export type { RagIngestionBatchBackoff, RagIngestionBatchStateUpdate };
