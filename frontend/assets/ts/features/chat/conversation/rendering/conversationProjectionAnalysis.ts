/* SoAI - Conversation projection analysis shared by chat entry projection and comparison selection [frontend/assets/ts/features/chat/conversation/rendering/conversationProjectionAnalysis.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import { resolveChatComparisonTurnMeta, resolveComparisonTurnStatesByTurn, type ChatComparisonTurnMeta, type ChatComparisonTurnState } from '@features/chat/comparisonTurnMetadata.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatTurnAdmissionStreamIdentity } from '@features/chat/chatstreamservice/types.ts';
import { resolveActiveStreamingAssistantSelection, type ActiveComparisonRun, type ActiveStreamingAssistantMeta, type TerminalRenderPendingPredicate } from '@features/chat/message/activeStreamingAssistantMessage.ts';
import { isEmptyAssistantPlaceholderMessage } from '@features/chat/message/placeholderAssistantMessage.ts';
import { resolveLastNonSystemMessageIndex, shouldRenderAssistantPlaceholder } from '@features/chat/conversation/rendering/assistantPlaceholderPolicy.ts';
import { resolveConversationMessageRenderPresentations, type ChatMessageRenderPresentation, type MessagePendingDeletionPredicate } from '@features/chat/message/messageRenderPresentation.ts';

type AssistantMessageByVariant = ReadonlyMap<number, { message: ChatMessage; messageIndex: number }>;

interface ConversationProjectionAnalysis {
    messages: readonly ChatMessage[];
    lastNonSystemIndex: number;
    logicalMessageCount: number;
    assistantMessagesByTurnAndVariant: ReadonlyMap<number, AssistantMessageByVariant>;
    comparisonMetaByMessageIndex: readonly (ChatComparisonTurnMeta | null)[];
    comparisonStatesByTurn: ReadonlyMap<number, ChatComparisonTurnState>;
    streamingAssistantMeta: ActiveStreamingAssistantMeta | null;
    isCurrentStreaming: boolean;
    activeComparisonRun: ActiveComparisonRun | null;
    messageRenderPresentations: readonly ChatMessageRenderPresentation[];
}

const analyzeConversationProjection = (
    conversation: ConversationContract | null,
    inputArguments: {
        isCurrentStreaming: boolean;
        activeComparisonRun: ActiveComparisonRun | null;
        activeStreamIdentity: ChatTurnAdmissionStreamIdentity | null;
        isMessagePendingDeletion: MessagePendingDeletionPredicate;
        isTerminalRenderPending?: TerminalRenderPendingPredicate;
    }
): ConversationProjectionAnalysis => {
    const messages = conversation && isArray(conversation.messages) ? conversation.messages : [];
    const lastNonSystemIndex = resolveLastNonSystemMessageIndex(messages);
    const comparisonMetaByMessageIndex = new Array<ChatComparisonTurnMeta | null>(messages.length).fill(null);
    const assistantMessagesByTurnAndVariant = new Map<number, Map<number, { message: ChatMessage; messageIndex: number }>>();
    const logicalAssistantTurns = new Set<number>();
    let logicalNonAssistantCount = 0;

    for (let messageIndex = 0; messageIndex < messages.length; messageIndex += 1) {
        const raw = messages[messageIndex];
        if (!raw || raw.role === 'system') {
            continue;
        }
        const message = raw;
        if (message.role !== 'assistant') {
            if (!isEmptyAssistantPlaceholderMessage(message)) {
                logicalNonAssistantCount += 1;
            }
            continue;
        }

        const meta = resolveChatComparisonTurnMeta(message);
        if (!meta) {
            throw new Error('ChatPage assistant message is missing comparison metadata');
        }
        comparisonMetaByMessageIndex[messageIndex] = meta;
        const byVariant = assistantMessagesByTurnAndVariant.get(meta.assistantTurnTimestamp);
        if (byVariant) {
            byVariant.set(meta.modelVariantIndex, { message, messageIndex });
        } else {
            assistantMessagesByTurnAndVariant.set(meta.assistantTurnTimestamp, new Map([[meta.modelVariantIndex, { message, messageIndex }]]));
        }
        if (shouldRenderAssistantPlaceholder(message, messageIndex, { isCurrentStreaming: inputArguments.isCurrentStreaming, lastNonSystemIndex })) {
            logicalAssistantTurns.add(meta.assistantTurnTimestamp);
        }
    }

    const activeStreamingSelection = resolveActiveStreamingAssistantSelection(conversation, {
        isConversationStreaming: inputArguments.isCurrentStreaming,
        activeComparisonRun: inputArguments.activeComparisonRun,
        activeStreamIdentity: inputArguments.activeStreamIdentity,
        ...(inputArguments.isTerminalRenderPending !== undefined ? { isTerminalRenderPending: inputArguments.isTerminalRenderPending } : {})
    });
    const messageRenderPresentations = resolveConversationMessageRenderPresentations(conversation, {
        activeStreamingAssistantDomIds: activeStreamingSelection.domIds,
        isMessagePendingDeletion: inputArguments.isMessagePendingDeletion
    });
    return {
        messages,
        lastNonSystemIndex,
        logicalMessageCount: logicalNonAssistantCount + logicalAssistantTurns.size,
        assistantMessagesByTurnAndVariant,
        comparisonMetaByMessageIndex,
        comparisonStatesByTurn: resolveComparisonTurnStatesByTurn(comparisonMetaByMessageIndex),
        streamingAssistantMeta: activeStreamingSelection.meta,
        isCurrentStreaming: inputArguments.isCurrentStreaming,
        activeComparisonRun: inputArguments.activeComparisonRun,
        messageRenderPresentations
    };
};

export { analyzeConversationProjection };
export type { AssistantMessageByVariant, ConversationProjectionAnalysis };
