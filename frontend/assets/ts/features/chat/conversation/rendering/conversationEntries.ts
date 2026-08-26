/* SoAI - Chat feature conversation entries [frontend/assets/ts/features/chat/conversation/rendering/conversationEntries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject } from '@core/typeGuards.ts';
import type { ChatComparisonTurnInvalidReason } from '@features/chat/comparisonTurnMetadata.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { resolveMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { isEmptyAssistantPlaceholderMessage } from '@features/chat/message/placeholderAssistantMessage.ts';
import { shouldRenderAssistantPlaceholder } from '@features/chat/conversation/rendering/assistantPlaceholderPolicy.ts';
import { buildComparisonTurnDomId, buildComparisonVariantEntries, resolveActiveVariantIndexByTurn, type ComparisonTurnVariantEntry } from '@features/chat/conversation/rendering/conversationComparisonEntries.ts';
import type { ConversationProjectionAnalysis } from '@features/chat/conversation/rendering/conversationProjectionAnalysis.ts';
import type { ChatMessageRenderPresentation } from '@features/chat/message/messageRenderPresentation.ts';

type MessageRenderEntry = {
    type: 'message';
    message: ChatMessage;
    index: number;
    domId: string;
    comparisonTurn: ChatComparisonTurnRenderModel | null;
    isActiveStreamingEntry: boolean;
    presentation: ChatMessageRenderPresentation;
};

type ComparisonTurnRenderEntry = {
    type: 'comparisonTurn';
    domId: string;
    assistantTurnTimestamp: number;
    variantCount: number;
    activeVariantIndex: number;
    invalidReason: ChatComparisonTurnInvalidReason | null;
    variants: ComparisonTurnVariantEntry[];
};

type ConversationRenderEntry = MessageRenderEntry | ComparisonTurnRenderEntry;

const resolveRenderableConversationEntries = (
    analysis: ConversationProjectionAnalysis,
    inputArguments: {
        activeVariantIndexByAssistantTurnTimestamp: ReadonlyMap<number, number> | null;
        includeEmptyAssistantPlaceholder?: (message: ChatMessage) => boolean;
    }
): ConversationRenderEntry[] => {
    const activeVariantIndexByTurn = resolveActiveVariantIndexByTurn({
        assistantVariantsByTurn: analysis.assistantMessagesByTurnAndVariant,
        statesByTurn: analysis.comparisonStatesByTurn,
        preferredActiveVariantIndexByAssistantTurnTimestamp: inputArguments.activeVariantIndexByAssistantTurnTimestamp
    });

    const renderedTurns = new Set<number>();
    const list: ConversationRenderEntry[] = [];
    for (let messageIndex = 0; messageIndex < analysis.messages.length; messageIndex += 1) {
        const raw = analysis.messages[messageIndex];
        if (!raw || !isObject(raw)) {
            continue;
        }
        if (raw['role'] === 'system') {
            continue;
        }
        if (!isChatMessage(raw)) {
            throw new Error('ChatPage cannot render a non-chat message object');
        }
        const message: ChatMessage = raw;
        const presentation = analysis.messageRenderPresentations[messageIndex];
        if (!presentation) {
            throw new Error('ChatPage message render presentation is missing');
        }

        if (message.role === 'assistant') {
            const meta = analysis.comparisonMetaByMessageIndex[messageIndex] ?? null;
            if (!meta) {
                throw new Error('ChatPage assistant message is missing comparison metadata');
            }
            if (renderedTurns.has(meta.assistantTurnTimestamp)) {
                continue;
            }
            const state = analysis.comparisonStatesByTurn.get(meta.assistantTurnTimestamp) ?? null;
            if (state === null) {
                throw new Error('ChatPage assistant comparison-turn state is missing');
            }

            const activeVariantIndex = activeVariantIndexByTurn.get(meta.assistantTurnTimestamp) ?? 0;
            const expectedVariantCount = analysis.activeComparisonRun && analysis.activeComparisonRun.assistantTurnTimestamp === meta.assistantTurnTimestamp ? analysis.activeComparisonRun.variantCount : null;
            const effectiveVariantCount = state.invalidReason === null ? Math.max(state.comparisonVariantTotal, expectedVariantCount ?? 1) : 1;
            const shouldRenderCarousel = state.invalidReason === null && effectiveVariantCount > 1;

            if (shouldRenderCarousel) {
                const byVariant = analysis.assistantMessagesByTurnAndVariant.get(meta.assistantTurnTimestamp) ?? new Map<number, { message: ChatMessage; messageIndex: number }>();
                const variants = buildComparisonVariantEntries({
                    assistantTurnTimestamp: meta.assistantTurnTimestamp,
                    slideCount: effectiveVariantCount,
                    navigationVariantCount: state.comparisonVariantTotal,
                    activeVariantIndex,
                    invalidReason: null,
                    messageByVariantIndex: byVariant,
                    isCurrentStreaming: analysis.isCurrentStreaming,
                    lastNonSystemIndex: analysis.lastNonSystemIndex,
                    activeComparisonRun: analysis.activeComparisonRun,
                    messageRenderPresentations: analysis.messageRenderPresentations,
                    ...(inputArguments.includeEmptyAssistantPlaceholder === undefined ? {} : { includeEmptyAssistantPlaceholder: inputArguments.includeEmptyAssistantPlaceholder })
                });
                renderedTurns.add(meta.assistantTurnTimestamp);
                list.push({
                    type: 'comparisonTurn',
                    domId: buildComparisonTurnDomId(meta.assistantTurnTimestamp),
                    assistantTurnTimestamp: meta.assistantTurnTimestamp,
                    variantCount: effectiveVariantCount,
                    activeVariantIndex,
                    invalidReason: null,
                    variants
                });
                continue;
            }

            if (meta.modelVariantIndex !== activeVariantIndex) {
                continue;
            }
            if (!shouldRenderAssistantPlaceholder(message, messageIndex, { isCurrentStreaming: analysis.isCurrentStreaming, lastNonSystemIndex: analysis.lastNonSystemIndex }) && inputArguments.includeEmptyAssistantPlaceholder?.(message) !== true) {
                continue;
            }
            renderedTurns.add(meta.assistantTurnTimestamp);
            const shouldExposeComparisonTurn = state.comparisonVariantTotal > 1 || state.invalidReason !== null;
            const domId = resolveMessageDomId(message, messageIndex);
            list.push({
                type: 'message',
                message,
                index: messageIndex,
                domId,
                isActiveStreamingEntry: presentation.isActiveStreamingAssistant,
                presentation,
                comparisonTurn: shouldExposeComparisonTurn
                    ? {
                          assistantTurnTimestamp: meta.assistantTurnTimestamp,
                          modelVariantIndex: meta.modelVariantIndex,
                          activeVariantIndex,
                          variantCount: state.comparisonVariantTotal,
                          invalidReason: state.invalidReason
                      }
                    : null
            });
            continue;
        }

        if (isEmptyAssistantPlaceholderMessage(message)) {
            continue;
        }
        list.push({
            type: 'message',
            message,
            index: messageIndex,
            domId: resolveMessageDomId(message, messageIndex),
            isActiveStreamingEntry: false,
            presentation,
            comparisonTurn: null
        });
    }

    return list;
};

export { resolveRenderableConversationEntries };
export type { ComparisonTurnRenderEntry, ComparisonTurnVariantEntry, ConversationRenderEntry, MessageRenderEntry };
