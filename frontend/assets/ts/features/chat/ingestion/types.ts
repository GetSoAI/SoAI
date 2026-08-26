/* SoAI - Chat feature ingestion contracts [frontend/assets/ts/features/chat/ingestion/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';

export type RagIngestionState = 'running' | 'paused' | 'submitted' | 'cancelled';
export type RagIngestionAttachmentSource = 'composer_document_upload' | 'composer_folder_upload' | 'knowledge_tab_document_upload' | 'knowledge_tab_folder_upload';

export type RagIngestionStatus = {
    conversationId: string;
    clientBatchId: string | null;
    state: RagIngestionState;
    total: number;
    queued: number;
    inFlight: number;
    succeeded: number;
    failed: number;
    skipped: number;
    lastError: string | null;
    knowledgeAttachment: KnowledgeAttachmentSummary | null;
};
