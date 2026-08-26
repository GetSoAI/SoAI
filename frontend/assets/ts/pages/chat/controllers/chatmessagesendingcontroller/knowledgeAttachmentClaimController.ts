/* SoAI - Chat knowledge attachment claim controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/knowledgeAttachmentClaimController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runWithAbortSignalScope } from '@core/errors/abort.ts';
import type { KnowledgeAttachmentCollectionResponse, KnowledgeAttachmentClaimResponse } from '@core/api/contracts/webuiAttachmentContracts.ts';
import type { ComposerPayload } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';
import { assertDraftKnowledgeAttachmentsAreTerminal, parseDraftKnowledgeAttachmentSelections, resolveDraftKnowledgeAttachmentSnapshot } from '@pages/chat/controllers/chatmessagesendingcontroller/knowledgeAttachmentDraftManager.ts';
import type { MessageSendingHost } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

const parseClaimedKnowledgeContentParts = (payload: KnowledgeAttachmentClaimResponse): KnowledgeAttachmentClaimResponse['contentParts'] => [...payload.contentParts];

const loadDraftKnowledgeAttachments = async (host: MessageSendingHost, conversationId: string, extraSignal: AbortSignal | null): Promise<KnowledgeAttachmentCollectionResponse> => {
    const response = await runWithAbortSignalScope([host.platform.getRuntimeAbortSignal(), extraSignal], (signal) => host.platform.runWithBoundary('chat:listDraftKnowledgeAttachments', () => host.services.getChatApi().webui.chat.attachments.knowledge.draft(conversationId, { previewLimit: 0, signal })));
    return response;
};

const claimDraftKnowledgeAttachments = async (host: MessageSendingHost, conversationId: string, payload: ComposerPayload, extraSignal: AbortSignal | null = null): Promise<ComposerPayload | null> => {
    const draftPayload = await loadDraftKnowledgeAttachments(host, conversationId, extraSignal);
    assertDraftKnowledgeAttachmentsAreTerminal(draftPayload);
    const draftSnapshot = resolveDraftKnowledgeAttachmentSnapshot(draftPayload);
    const selections = parseDraftKnowledgeAttachmentSelections(draftPayload);
    if (selections.length === 0) {
        return payload;
    }
    const claimedPayload = await runWithAbortSignalScope([host.platform.getRuntimeAbortSignal(), extraSignal], (signal) => host.platform.runWithBoundary('chat:claimDraftKnowledgeAttachments', () => host.services.getChatApi().webui.chat.attachments.knowledge.claim(conversationId, { selections }, { signal })));
    const claimedParts = parseClaimedKnowledgeContentParts(claimedPayload);
    const remainingDraftPayload = await loadDraftKnowledgeAttachments(host, conversationId, extraSignal);
    if (resolveDraftKnowledgeAttachmentSnapshot(remainingDraftPayload) !== draftSnapshot) {
        return null;
    }
    return {
        ...payload,
        attachmentContent: [...payload.attachmentContent, ...claimedParts]
    };
};

export { claimDraftKnowledgeAttachments };
