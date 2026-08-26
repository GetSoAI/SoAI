/* SoAI - Chat feature RAG ingestion batch upload [frontend/assets/ts/features/chat/ragingestion/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RagBatchUploadOptions } from '@core/api/endpoints/webuiRagUploads.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import type { RagBatchUploadResponse } from '@core/api/contracts/webuiRagContracts.ts';
import type { RagIngestionStatus } from '@features/chat/public.ts';
import { applyFailedRagIngestionBatchUpload, applySuccessfulRagIngestionBatchUpload, type RagIngestionBatchBackoff, type RagIngestionBatchStateUpdate } from '@features/chat/ragingestion/batchupload/state.ts';
import { type RagIngestionQueueLease, RagIngestionQueuePacer } from '@features/chat/ragingestion/queue/service.ts';

interface UploadRagIngestionBatchArguments {
    status: RagIngestionStatus;
    files: File[];
    queuePacer: RagIngestionQueuePacer;
    backoff: RagIngestionBatchBackoff;
    isStopped: () => boolean;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    uploadDocumentsBatch: (conversationId: string, files: readonly File[], options?: RagBatchUploadOptions) => Promise<RagBatchUploadResponse>;
    uploadOptions: RagBatchUploadOptions;
}

const uploadRagIngestionBatch = async (inputArguments: UploadRagIngestionBatchArguments): Promise<RagIngestionBatchStateUpdate | null> => {
    let queueLease: RagIngestionQueueLease | null = null;
    try {
        queueLease = await inputArguments.queuePacer.reserve(inputArguments.status.conversationId, inputArguments.files.length, inputArguments.isStopped);
        if (!queueLease) {
            return null;
        }
        const payload = await inputArguments.runWithBoundary('chat:ragIngestionUpload', () => inputArguments.uploadDocumentsBatch(inputArguments.status.conversationId, inputArguments.files, inputArguments.uploadOptions));
        if (inputArguments.isStopped()) {
            return null;
        }
        return applySuccessfulRagIngestionBatchUpload({ status: inputArguments.status, files: inputArguments.files, payload, backoff: inputArguments.backoff });
    } catch (error) {
        if (inputArguments.isStopped()) {
            ensureError(error);
            return null;
        }
        const runtimeError = ensureError(error);
        notifyHandledOperationError(runtimeError);
        return applyFailedRagIngestionBatchUpload({ status: inputArguments.status, files: inputArguments.files, error: runtimeError, backoff: inputArguments.backoff });
    } finally {
        if (queueLease) {
            queueLease.release();
        }
    }
};

export { uploadRagIngestionBatch };
