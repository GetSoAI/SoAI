/* SoAI - Chat feature logical message count [frontend/assets/ts/features/chat/conversation/rendering/logicalMessageCount.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import { resolveChatComparisonTurnMeta } from '@features/chat/comparisonTurnMetadata.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { isEmptyAssistantPlaceholderMessage } from '@features/chat/message/placeholderAssistantMessage.ts';
import { resolveLastNonSystemMessageIndex, shouldRenderAssistantPlaceholder } from '@features/chat/conversation/rendering/assistantPlaceholderPolicy.ts';

const countLogicalConversationMessages = (conversation: ConversationContract | null, inputArguments: { isCurrentStreaming: boolean }): number => {
    const messages = conversation && isArray(conversation.messages) ? conversation.messages : [];
    const lastNonSystemIndex = resolveLastNonSystemMessageIndex(messages);
    const assistantTurns = new Set<number>();
    let nonAssistantCount = 0;
    for (let index = 0; index < messages.length; index += 1) {
        const raw = messages[index];
        if (!raw) {
            continue;
        }
        if (raw.role === 'system') {
            continue;
        }
        const message: ChatMessage = raw;
        if (message.role === 'assistant') {
            if (!shouldRenderAssistantPlaceholder(message, index, { isCurrentStreaming: inputArguments.isCurrentStreaming, lastNonSystemIndex })) {
                continue;
            }
            const meta = resolveChatComparisonTurnMeta(message);
            if (!meta) {
                throw new Error('ChatPage assistant message is missing comparison metadata');
            }
            assistantTurns.add(meta.assistantTurnTimestamp);
            continue;
        }
        if (isEmptyAssistantPlaceholderMessage(message)) {
            continue;
        }
        nonAssistantCount += 1;
    }
    return nonAssistantCount + assistantTurns.size;
};

export { countLogicalConversationMessages };
