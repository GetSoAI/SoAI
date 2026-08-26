/* SoAI - Frontend WebUI attachment response serialization [frontend/assets/ts/core/api/contracts/webuiAttachmentSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentClaimRequest, KnowledgeAttachmentPreviewRequest, KnowledgeAttachmentSummary, KnowledgeAttachmentUseRequest } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeKnowledgeAttachmentSummary = (summary: KnowledgeAttachmentSummary): JsonObject => ({
    'knowledge_attachment_id': summary.knowledgeAttachmentId,
    'summary_id': summary.summaryId,
    'conv_id': summary.convId,
    'user_id': summary.userId,
    state: summary.state,
    'conversation_input_id': summary.conversationInputId,
    'message_created_at_ms': summary.messageCreatedAtMs,
    'processing_state': summary.processingState,
    'source_type': summary.sourceType,
    'operation_type': summary.operationType,
    title: summary.title,
    'root_label': summary.rootLabel,
    'root_virtual_path': summary.rootVirtualPath,
    'task_id': summary.taskId,
    'client_batch_id': summary.clientBatchId,
    'first_event_id': summary.firstEventId,
    'last_event_id': summary.lastEventId,
    'state_signature': summary.stateSignature,
    'total_count': summary.totalCount,
    'visible_count': summary.visibleCount,
    'hidden_count': summary.hiddenCount,
    'status_counts': { ...summary.statusCounts },
    'attachment_revision': summary.attachmentRevision,
    'created_at_ms': summary.createdAtMs,
    'updated_at_ms': summary.updatedAtMs,
    'finalized_at_ms': summary.finalizedAtMs,
    'expires_at_ms': summary.expiresAtMs
});

const serializeKnowledgeAttachmentClaimRequest = (request: KnowledgeAttachmentClaimRequest): JsonObject => ({
    selections: request.selections.map((selection) => ({ 'knowledge_attachment_id': selection.knowledgeAttachmentId, 'attachment_revision': selection.attachmentRevision }))
});

const serializeKnowledgeAttachmentPreviewRequest = (request: KnowledgeAttachmentPreviewRequest): JsonObject => ({ 'document_id': request.documentId });

const serializeKnowledgeAttachmentUseRequest = (request: KnowledgeAttachmentUseRequest): JsonObject => ({
    'source_conv_id': request.sourceConvId,
    'source_knowledge_attachment_id': request.sourceKnowledgeAttachmentId,
    selections: request.selections.map((selection) => ({ 'item_id': selection.itemId, 'document_id': selection.documentId })),
    'client_batch_id': request.clientBatchId
});

export { serializeKnowledgeAttachmentClaimRequest, serializeKnowledgeAttachmentPreviewRequest, serializeKnowledgeAttachmentSummary, serializeKnowledgeAttachmentUseRequest };
