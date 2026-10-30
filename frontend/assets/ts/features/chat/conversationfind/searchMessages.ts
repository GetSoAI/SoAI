/* SoAI - Canonical searchable message and comparison ordering [frontend/assets/ts/features/chat/conversationfind/searchMessages.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveRenderableConversationEntries } from '@features/chat/conversation/rendering/conversationEntries.ts';
import { analyzeConversationProjection } from '@features/chat/conversation/rendering/conversationProjectionAnalysis.ts';
import { isSearchableChatMessage } from '@features/chat/message/searchTextPolicy.ts';

const resolveConversationFindMessages = (messages: readonly ChatMessage[]): { message: ChatMessage; orderMessage: ChatMessage }[] => {
    const analysis = analyzeConversationProjection({ messages: messages.filter(isSearchableChatMessage) }, { isCurrentStreaming: false, activeComparisonRun: null, activeStreamIdentity: null, isMessagePendingDeletion: () => false });
    const entries = resolveRenderableConversationEntries(analysis, { activeVariantIndexByAssistantTurnTimestamp: null });
    const result: { message: ChatMessage; orderMessage: ChatMessage }[] = [];
    for (const entry of entries) {
        if (entry.type === 'message') {
            if (!entry.comparisonTurn?.invalidReason) result.push({ message: entry.message, orderMessage: entry.message });
        } else {
            const orderMessage = entry.variants[0]?.message;
            if (entry.invalidReason !== null || !orderMessage) continue;
            for (const variant of entry.variants) {
                if (variant.message) result.push({ message: variant.message, orderMessage });
            }
        }
    }
    return result;
};

export { resolveConversationFindMessages };
