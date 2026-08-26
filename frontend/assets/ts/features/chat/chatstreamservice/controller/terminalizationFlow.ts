/* SoAI - Chat feature terminalization flow [frontend/assets/ts/features/chat/chatstreamservice/controller/terminalizationFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DeferredRejectionReason } from '@core/runtime/deferred.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveChatComparisonTurnMeta } from '@features/chat/comparisonTurnMetadata.ts';
import { dropPendingStreamRender, getConversationStreamState } from '@features/chat/chatstreamservice/controller/state.ts';
import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';
import { buildComparisonVariantRequestId } from '@features/chat/chatstreamservice/comparisonRequestIdentity.ts';
import { clearConversationTerminalizationPromiseState } from '@features/chat/chatstreamservice/controller/terminalizationState.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const buildTerminalizationKey = (inputArguments: { requestId: string | null; assistantTimestamp: number }): string => {
    const requestId = inputArguments.requestId === null ? 'null' : inputArguments.requestId;
    return `${requestId}:${String(inputArguments.assistantTimestamp)}`;
};

const isTerminalizationWaiterCurrent = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; terminalizationKey: string; resolve: () => void; reject: (error: DeferredRejectionReason) => void }): boolean => {
    const state = getConversationStreamState(context, inputArguments.conversationId);
    return Boolean(state && state.terminalizationResolve === inputArguments.resolve && state.terminalizationReject === inputArguments.reject && state.terminalizationPromiseKey === inputArguments.terminalizationKey);
};

const deleteIdleTerminalizationState = (context: ChatStreamingControllerContext, conversationId: string): void => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (normalizedConversationId === null) {
        return;
    }
    const state = getConversationStreamState(context, normalizedConversationId);
    const shouldRemoveIdleState = state !== null && state.phase === 'idle' && state.activityRefreshTimerId === null && state.terminalRenderTimerId === null && !context.dependencies.chatStreamService.isStreaming(normalizedConversationId);
    if (shouldRemoveIdleState) {
        context.streamStateByConversationId.delete(normalizedConversationId);
    }
};

const settleTerminalizationWaiter = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; terminalizationKey: string; resolve: () => void; reject: (error: DeferredRejectionReason) => void; error?: DeferredRejectionReason }): void => {
    if (!isTerminalizationWaiterCurrent(context, inputArguments)) {
        return;
    }
    const state = getConversationStreamState(context, inputArguments.conversationId);
    if (!state) {
        return;
    }
    clearConversationTerminalizationPromiseState(state);
    deleteIdleTerminalizationState(context, inputArguments.conversationId);
    if (inputArguments.error !== undefined) {
        inputArguments.reject(inputArguments.error);
        return;
    }
    inputArguments.resolve();
};

const shouldKeepStreamingUiActiveAfterTerminal = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; requestId: string | null; assistantTimestamp: number; assistantMessage: ChatMessage | null; status: 'complete' | 'error' | 'cancelled' }): boolean => {
    if (inputArguments.status !== 'complete') {
        return false;
    }
    const state = getConversationStreamState(context, inputArguments.conversationId);
    if (!state || state.phase === 'idle') {
        return false;
    }
    const comparisonRun = state.comparisonRun;
    if (!comparisonRun || comparisonRun.aborting || comparisonRun.variantCount <= 1 || !inputArguments.assistantMessage) {
        return false;
    }
    const comparisonMeta = resolveChatComparisonTurnMeta(inputArguments.assistantMessage);
    if (!comparisonMeta || comparisonMeta.assistantTurnTimestamp !== comparisonRun.assistantTurnTimestamp) {
        return false;
    }
    const variantIndex = comparisonMeta.modelVariantIndex;
    if (variantIndex >= comparisonRun.variantCount) {
        return false;
    }
    const expectedRequestId = buildComparisonVariantRequestId(comparisonRun.groupRequestId, variantIndex);
    if (!inputArguments.requestId || inputArguments.requestId !== expectedRequestId) {
        return false;
    }
    return variantIndex < comparisonRun.variantCount - 1;
};

const hasTerminalStateMismatch = (state: { requestId: string | null; assistantTimestamp: number | null }, inputArguments: { requestId: string | null; assistantTimestamp: number }): boolean => {
    return (inputArguments.requestId !== null && state.requestId !== null && inputArguments.requestId !== state.requestId) || (state.assistantTimestamp !== null && inputArguments.assistantTimestamp !== state.assistantTimestamp);
};

const prepareCurrentConversationForTerminalization = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; assistantMessage: ChatMessage | null }): void => {
    const currentConversationId = context.dependencies.state.getCurrentConversationId();
    if (currentConversationId !== inputArguments.conversationId || inputArguments.assistantMessage === null) {
        return;
    }
    dropPendingStreamRender(context, inputArguments.assistantMessage, inputArguments.conversationId);
};

export { buildTerminalizationKey, deleteIdleTerminalizationState, hasTerminalStateMismatch, isTerminalizationWaiterCurrent, prepareCurrentConversationForTerminalization, settleTerminalizationWaiter, shouldKeepStreamingUiActiveAfterTerminal };
