/* SoAI - Chat feature RAG ingestion task operation manager [frontend/assets/ts/features/chat/ragingestion/RagIngestionTaskOperationManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { syncRagUploadProgress, type RagIngestionStatus } from '@features/chat/public.ts';

const syncRagIngestionTaskOperation = (status: RagIngestionStatus | null, cancel: (conversationId: string) => Promise<void>): void => {
    syncRagUploadProgress(
        status?.conversationId ?? null,
        status,
        status && status.state !== 'submitted' && status.state !== 'cancelled'
            ? () => {
                  void cancel(status.conversationId).catch((error) => {
                      errorHandler.error('RagIngestionTaskOperationManager', 'Failed to cancel RAG ingestion', ensureError(error));
                  });
              }
            : null
    );
};

const RagIngestionTaskOperationManager = {
    syncRagIngestionTaskOperation
};

export { RagIngestionTaskOperationManager, syncRagIngestionTaskOperation };
