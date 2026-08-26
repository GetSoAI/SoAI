/* SoAI - Chat knowledge attachment draft manager [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/knowledgeAttachmentDraftManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentCollectionResponse, KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { serializeKnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentSerialization.ts';
import { i18n } from '@core/i18n/index.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';

type KnowledgeAttachmentSelection = {
    knowledgeAttachmentId: string;
    attachmentRevision: number;
};

const CLAIMABLE_PROCESSING_STATES = new Set(['ready', 'error', 'cancelled']);
const NONTERMINAL_PROCESSING_STATES = new Set(['pending', 'running', 'cancelling']);

const parseDraftKnowledgeAttachmentSelection = (summary: KnowledgeAttachmentSummary): KnowledgeAttachmentSelection | null => {
    if (!CLAIMABLE_PROCESSING_STATES.has(summary.processingState)) {
        return null;
    }
    return {
        knowledgeAttachmentId: summary.knowledgeAttachmentId,
        attachmentRevision: summary.attachmentRevision
    };
};

const parseDraftKnowledgeAttachmentSelections = (payload: KnowledgeAttachmentCollectionResponse): KnowledgeAttachmentSelection[] => {
    const selections: KnowledgeAttachmentSelection[] = [];
    for (const summary of payload.items) {
        const selection = parseDraftKnowledgeAttachmentSelection(summary);
        if (selection !== null) selections.push(selection);
    }
    return selections;
};

const assertDraftKnowledgeAttachmentsAreTerminal = (payload: KnowledgeAttachmentCollectionResponse): void => {
    for (const summary of payload.items) {
        if (NONTERMINAL_PROCESSING_STATES.has(summary.processingState)) {
            throw new Error(i18n.t('chat.attachments.knowledgeStillProcessing'));
        }
    }
};

const hasClaimableDraftKnowledgeAttachment = (payload: KnowledgeAttachmentCollectionResponse): boolean => {
    assertDraftKnowledgeAttachmentsAreTerminal(payload);
    return parseDraftKnowledgeAttachmentSelections(payload).length > 0;
};

const resolveDraftKnowledgeAttachmentSnapshot = (payload: KnowledgeAttachmentCollectionResponse): string => {
    const itemSignatures = payload.items.map((summary) => stableJsonStringify(serializeKnowledgeAttachmentSummary(summary)));
    itemSignatures.sort((left, right) => (left < right ? -1 : left > right ? 1 : 0));
    return stableJsonStringify(itemSignatures);
};

export { assertDraftKnowledgeAttachmentsAreTerminal, hasClaimableDraftKnowledgeAttachment, parseDraftKnowledgeAttachmentSelections, resolveDraftKnowledgeAttachmentSnapshot };
export type { KnowledgeAttachmentSelection };
