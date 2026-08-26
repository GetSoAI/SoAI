/* SoAI - RAG ingestion cancellation status resolution [frontend/assets/ts/features/chat/ragingestion/cancellation/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeConversationId, type RagIngestionStatus } from '@features/chat/public.ts';

const resolveKnowledgeAttachmentIdForCancellation = (status: RagIngestionStatus): string | null => {
    const knowledgeAttachment = status.knowledgeAttachment;
    return knowledgeAttachment?.knowledgeAttachmentId ?? null;
};

const resolveCancelledIngestionStatus = (status: RagIngestionStatus | null, conversationId: string, inFlight: number): RagIngestionStatus | null => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId || !status || status.conversationId !== normalizedConversationId) {
        return null;
    }
    if (status.state === 'cancelled') {
        return null;
    }
    return {
        ...status,
        state: 'cancelled',
        queued: 0,
        inFlight: inFlight
    };
};

export { resolveCancelledIngestionStatus, resolveKnowledgeAttachmentIdForCancellation };
