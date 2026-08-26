/* SoAI - Chat feature entry signatures [frontend/assets/ts/features/chat/conversation/rendering/entrySignatures.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveChatMessageActiveStreamingSignature, resolveChatMessageRenderCacheSignature, resolveChatMessageRenderSignature } from '@features/chat/message/messageRenderSignature.ts';
import type { ComparisonTurnRenderEntry, ConversationRenderEntry, MessageRenderEntry } from '@features/chat/conversation/rendering/conversationEntries.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';

const resolveSettledMessageFingerprint = (message: ChatMessage, comparisonTurn: ChatComparisonTurnRenderModel | null): string => resolveChatMessageRenderSignature(message, comparisonTurn);

const resolveConversationEntrySignature = (entry: MessageRenderEntry, inputArguments: { isCurrentStreaming: boolean }): string => {
    if (inputArguments.isCurrentStreaming && entry.isActiveStreamingEntry) {
        return `${entry.domId}|${resolveChatMessageActiveStreamingSignature(entry.message, entry.comparisonTurn)}`;
    }
    return resolveChatMessageRenderCacheSignature(entry.domId, entry.message, entry.comparisonTurn);
};

const resolveComparisonTurnEntrySignature = (entry: ComparisonTurnRenderEntry, inputArguments: { isCurrentStreaming: boolean }): string => {
    const variants: string[] = [];
    for (const variant of entry.variants) {
        if (variant.message === null || variant.comparisonTurn === null) {
            variants.push(`v:${String(variant.variantIndex)}:missing`);
            continue;
        }
        const messageSignature = inputArguments.isCurrentStreaming && variant.isActiveStreamingEntry ? resolveChatMessageActiveStreamingSignature(variant.message, variant.comparisonTurn) : resolveChatMessageRenderSignature(variant.message, variant.comparisonTurn);
        variants.push(`v:${String(variant.variantIndex)}:${variant.domId ?? ''}:${messageSignature}`);
    }
    return `${entry.domId}|turn:${String(entry.assistantTurnTimestamp)}|count:${String(entry.variantCount)}|invalid:${entry.invalidReason ?? ''}|${variants.join('||')}`;
};

const resolveConversationRenderEntrySignature = (entry: ConversationRenderEntry, inputArguments: { isCurrentStreaming: boolean }): string => {
    if (entry.type === 'message') {
        return resolveConversationEntrySignature(entry, inputArguments);
    }
    return resolveComparisonTurnEntrySignature(entry, inputArguments);
};

export { resolveConversationRenderEntrySignature, resolveSettledMessageFingerprint };
