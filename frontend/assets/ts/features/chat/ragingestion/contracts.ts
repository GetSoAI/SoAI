/* SoAI - RAG ingestion controller contracts [frontend/assets/ts/features/chat/ragingestion/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestOptions } from '@core/api/types/request.ts';
import type { RagBatchUploadOptions } from '@core/api/endpoints/webuiRagUploads.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { RagBatchUploadResponse, RagDocumentsResponse } from '@core/api/contracts/webuiRagContracts.ts';
import type { RagIngestionAttachmentSource, RagIngestionStatus } from '@features/chat/public.ts';

type RagQueuedIngestionFile = {
    file: File;
    attachmentSource: RagIngestionAttachmentSource;
};

interface RagIngestionControllerDependencies {
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    listDocuments: (conversationId: string, options?: { limit?: number; offset?: number; includeDocuments?: boolean }) => Promise<RagDocumentsResponse>;
    uploadDocumentsBatch: (conversationId: string, files: readonly File[], options?: RagBatchUploadOptions) => Promise<RagBatchUploadResponse>;
    cancelKnowledgeAttachment: (conversationId: string, knowledgeAttachmentId: string, options?: RequestOptions) => Promise<KnowledgeAttachmentSummary>;
    resolveAbortSignal: () => AbortSignal | null;
    onStatusChange: (status: RagIngestionStatus | null) => void;
}

type StartIngestionArguments = {
    conversationId: string;
    files: File[];
    attachmentSource: RagIngestionAttachmentSource;
};

export type { RagIngestionControllerDependencies, RagQueuedIngestionFile, StartIngestionArguments };
