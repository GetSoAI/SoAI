/* SoAI - Comparison turn variant entry building for conversation rendering [frontend/assets/ts/features/chat/conversation/rendering/conversationComparisonEntries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { ChatComparisonTurnInvalidReason, ChatComparisonTurnState } from '@features/chat/comparisonTurnMetadata.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { AssistantMessageByVariant } from '@features/chat/conversation/rendering/conversationProjectionAnalysis.ts';
import type { ActiveComparisonRun } from '@features/chat/message/activeStreamingAssistantMessage.ts';
import { resolveMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { isEmptyAssistantPlaceholderMessage } from '@features/chat/message/placeholderAssistantMessage.ts';
import { shouldRenderAssistantPlaceholder } from '@features/chat/conversation/rendering/assistantPlaceholderPolicy.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import type { ChatMessageRenderPresentation } from '@features/chat/message/messageRenderPresentation.ts';

type ComparisonTurnVariantEntry = {
    variantIndex: number;
    message: ChatMessage | null;
    messageIndex: number | null;
    domId: string | null;
    comparisonTurn: ChatComparisonTurnRenderModel | null;
    isActiveStreamingEntry: boolean;
    presentation: ChatMessageRenderPresentation | null;
};

const resolveActiveVariantIndexByTurn = (inputArguments: { assistantVariantsByTurn: ReadonlyMap<number, AssistantMessageByVariant>; statesByTurn: ReadonlyMap<number, ChatComparisonTurnState>; preferredActiveVariantIndexByAssistantTurnTimestamp: ReadonlyMap<number, number> | null }): Map<number, number> => {
    const resolved = new Map<number, number>();
    for (const [assistantTurnTimestamp, state] of inputArguments.statesByTurn.entries()) {
        const variants = inputArguments.assistantVariantsByTurn.get(assistantTurnTimestamp);
        if (state.invalidReason !== null) {
            if (variants?.has(0) === true) {
                resolved.set(assistantTurnTimestamp, 0);
                continue;
            }
            const minIndex = variants && variants.size > 0 ? Math.min(...variants.keys()) : 0;
            resolved.set(assistantTurnTimestamp, minIndex);
            continue;
        }
        const preferred = inputArguments.preferredActiveVariantIndexByAssistantTurnTimestamp?.get(assistantTurnTimestamp) ?? 0;
        const maxIndex = Math.max(0, state.comparisonVariantTotal - 1);
        resolved.set(assistantTurnTimestamp, clampNumber(preferred, 0, maxIndex));
    }
    return resolved;
};

const buildComparisonTurnDomId = (assistantTurnTimestamp: number): string => `ct:${String(assistantTurnTimestamp)}`;

type EmptyAssistantPlaceholderResolver = (message: ChatMessage) => boolean;

type ComparisonVariantMessageRenderArguments = {
    message: ChatMessage;
    messageIndex: number;
    assistantTurnTimestamp: number;
    isCurrentStreaming: boolean;
    lastNonSystemIndex: number;
    activeComparisonRun: { assistantTurnTimestamp: number; variantCount: number } | null;
    includeEmptyAssistantPlaceholder?: EmptyAssistantPlaceholderResolver;
};

type BuildComparisonVariantEntriesArguments = {
    assistantTurnTimestamp: number;
    slideCount: number;
    navigationVariantCount: number;
    activeVariantIndex: number;
    invalidReason: ChatComparisonTurnInvalidReason | null;
    messageByVariantIndex: ReadonlyMap<number, { message: ChatMessage; messageIndex: number }>;
    isCurrentStreaming: boolean;
    lastNonSystemIndex: number;
    activeComparisonRun: ActiveComparisonRun | null;
    messageRenderPresentations: readonly ChatMessageRenderPresentation[];
    includeEmptyAssistantPlaceholder?: EmptyAssistantPlaceholderResolver;
};

const shouldRenderComparisonVariantMessage = (inputArguments: ComparisonVariantMessageRenderArguments): boolean => {
    if (!isEmptyAssistantPlaceholderMessage(inputArguments.message)) {
        return true;
    }
    if (inputArguments.includeEmptyAssistantPlaceholder?.(inputArguments.message) === true) {
        return true;
    }
    if (inputArguments.isCurrentStreaming && inputArguments.activeComparisonRun && inputArguments.activeComparisonRun.assistantTurnTimestamp === inputArguments.assistantTurnTimestamp) {
        return true;
    }
    return shouldRenderAssistantPlaceholder(inputArguments.message, inputArguments.messageIndex, {
        isCurrentStreaming: inputArguments.isCurrentStreaming,
        lastNonSystemIndex: inputArguments.lastNonSystemIndex
    });
};

const buildComparisonVariantEntries = (inputArguments: BuildComparisonVariantEntriesArguments): ComparisonTurnVariantEntry[] => {
    const variants: ComparisonTurnVariantEntry[] = [];
    for (let variantIndex = 0; variantIndex < inputArguments.slideCount; variantIndex += 1) {
        const resolved = inputArguments.messageByVariantIndex.get(variantIndex) ?? null;
        if (
            !resolved ||
            !shouldRenderComparisonVariantMessage({
                message: resolved.message,
                messageIndex: resolved.messageIndex,
                assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
                isCurrentStreaming: inputArguments.isCurrentStreaming,
                lastNonSystemIndex: inputArguments.lastNonSystemIndex,
                activeComparisonRun: inputArguments.activeComparisonRun,
                ...(inputArguments.includeEmptyAssistantPlaceholder === undefined ? {} : { includeEmptyAssistantPlaceholder: inputArguments.includeEmptyAssistantPlaceholder })
            })
        ) {
            variants.push({
                variantIndex,
                message: null,
                messageIndex: null,
                domId: null,
                comparisonTurn: null,
                isActiveStreamingEntry: false,
                presentation: null
            });
            continue;
        }
        const messageDomId = resolveMessageDomId(resolved.message, resolved.messageIndex);
        const presentation = inputArguments.messageRenderPresentations[resolved.messageIndex];
        if (!presentation) {
            throw new Error('ChatPage comparison message render presentation is missing');
        }
        variants.push({
            variantIndex,
            message: resolved.message,
            messageIndex: resolved.messageIndex,
            domId: messageDomId,
            comparisonTurn: {
                assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
                modelVariantIndex: variantIndex,
                activeVariantIndex: inputArguments.activeVariantIndex,
                variantCount: inputArguments.navigationVariantCount,
                invalidReason: inputArguments.invalidReason
            },
            isActiveStreamingEntry: presentation.isActiveStreamingAssistant,
            presentation
        });
    }
    return variants;
};

export { buildComparisonTurnDomId, buildComparisonVariantEntries, resolveActiveVariantIndexByTurn };
export type { ComparisonTurnVariantEntry };
