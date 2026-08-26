/* SoAI - RAG ingestion upload identity manager [frontend/assets/ts/features/chat/ragingestion/RagIngestionUploadIdentityManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { generateSecureId } from '@core/primitives/idGenerator.ts';
import type { RagIngestionAttachmentSource } from '@features/chat/public.ts';

type RagIngestionUploadIdentitySnapshot = {
    attachmentSource: RagIngestionAttachmentSource;
    clientBatchId: string;
};

class RagIngestionUploadIdentityManager {
    #clientBatchId: string | null = null;

    begin(resetBatch: boolean): string {
        if (resetBatch || this.#clientBatchId === null) {
            this.#clientBatchId = generateSecureId({ prefix: 'rag', format: 'hex', separator: '_' });
        }
        return this.#clientBatchId;
    }

    requireSnapshot(attachmentSource: RagIngestionAttachmentSource): RagIngestionUploadIdentitySnapshot {
        const clientBatchId = this.#clientBatchId;
        if (clientBatchId === null) {
            throw new Error('RAG ingestion upload identity is missing');
        }
        return { attachmentSource, clientBatchId };
    }

    clear(): void {
        this.#clientBatchId = null;
    }
}

export { RagIngestionUploadIdentityManager };
export type { RagIngestionUploadIdentitySnapshot };
