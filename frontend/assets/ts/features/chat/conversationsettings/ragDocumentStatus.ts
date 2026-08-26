/* SoAI - Chat feature conversation settings RAG document status [frontend/assets/ts/features/chat/conversationsettings/ragDocumentStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RagDocumentStatusCounts } from '@features/chat/conversationsettings/settingsModels.ts';

const RAG_PROCESSING_DOCUMENT_STATUSES: readonly string[] = ['queued', 'fetching', 'parsing', 'chunking', 'embedding'];

const isRagDocumentProcessingStatus = (status: string): boolean => {
    return RAG_PROCESSING_DOCUMENT_STATUSES.includes(status);
};

const countProcessingRagDocuments = (counts: RagDocumentStatusCounts): number => {
    return Math.max(0, counts.queued + counts.fetching + counts.parsing + counts.chunking + counts.embedding);
};

export { countProcessingRagDocuments, isRagDocumentProcessingStatus };
