/* SoAI - Terminal assistant message settlement for chat stream completion [frontend/assets/ts/features/chat/chatstreamservice/controller/terminalAssistantSettlement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isObject } from '@core/typeGuards.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { resolveChatComparisonTurnMeta } from '@features/chat/comparisonTurnMetadata.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import { getConversationStreamState } from '@features/chat/chatstreamservice/controller/state.ts';
import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';
import { patchRenderedAssistantMessageInConversation } from '@features/chat/message/assistantMessageDomPatch.ts';
import { findCanonicalAssistantMessage } from '@features/chat/chatstreamservice/controller/canonicalAssistantIdentity.ts';
import { resolveAssistantMutationPostRenderType } from '@features/chat/message/assistantMutationPostRenderPolicy.ts';
import { resolveSettledMessageFingerprint } from '@features/chat/conversation/rendering/entrySignatures.ts';
import { reconcileStreamingSpinnerStatusSubtree } from '@features/chat/stream/streamMessageSpinnerStatusRuntime.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { isChatMessageDomOwnedByLiveContainer } from '@features/chat/message/messageDomOwnership.ts';
import { canSerializeSettledAssistantBody } from '@features/chat/message/assistantSettledDom.ts';
import { buildAssistantBodyItems, resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';

type TerminalAssistantSettlementResult = {
    root: HTMLElement;
    messageDomId: string;
    changed: boolean;
    requiresPostRender: boolean;
};

type TerminalAssistantSettlementPlan = {
    assistantMessage: ChatMessage | null;
    comparisonTurn: ChatComparisonTurnRenderModel | null;
};

type TerminalAssistantSettlementReceipt = {
    root: HTMLElement;
    messageDomId: string;
    settledMarkup: string;
};

const resolveTerminalComparisonTurn = (context: ChatStreamingControllerContext, conversationId: string, message: ChatMessage): ChatComparisonTurnRenderModel | null => {
    const activeState = getConversationStreamState(context, conversationId);
    if (!activeState || !activeState.comparisonRun) {
        return null;
    }
    const meta = resolveChatComparisonTurnMeta(message);
    if (!meta || meta.assistantTurnTimestamp !== activeState.comparisonRun.assistantTurnTimestamp) {
        return null;
    }
    return {
        assistantTurnTimestamp: meta.assistantTurnTimestamp,
        modelVariantIndex: meta.modelVariantIndex,
        activeVariantIndex: meta.modelVariantIndex,
        variantCount: activeState.comparisonRun.variantCount,
        invalidReason: null
    };
};

const resolveTerminalAssistantSettlementPlan = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; assistantMessage: ChatMessage | null; activeConversationId: string | null }): TerminalAssistantSettlementPlan => {
    if (inputArguments.activeConversationId !== inputArguments.conversationId || inputArguments.assistantMessage === null) {
        return { assistantMessage: null, comparisonTurn: null };
    }
    const canonicalAssistantMessage = findCanonicalAssistantMessage(context.dependencies.conversations.get(inputArguments.conversationId), inputArguments.assistantMessage);
    if (canonicalAssistantMessage === null) {
        context.errorHandler?.error?.('ChatStream', `Canonical assistant message was not found after stream completion for ${inputArguments.conversationId}`);
        return { assistantMessage: null, comparisonTurn: null };
    }
    return {
        assistantMessage: canonicalAssistantMessage,
        comparisonTurn: resolveTerminalComparisonTurn(context, inputArguments.conversationId, canonicalAssistantMessage)
    };
};

const settleTerminalAssistantMessage = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; conversation: ConversationContract; message: ChatMessage; comparisonTurn: ChatComparisonTurnRenderModel | null; canonicalCorrection: boolean }): TerminalAssistantSettlementResult | null => {
    const updateConversationRenderCache = context.dependencies.presentation.updateConversationRenderCache;
    const host = {
        optionalUI: (selector: string, parent?: Element): Element | null => context.dependencies.presentation.optionalUI(selector, parent),
        messageManager: context.dependencies.messageManager,
        ...(typeof updateConversationRenderCache === 'function' ? { updateConversationRenderCache } : {})
    };
    const patch = {
        conversation: inputArguments.conversation,
        conversationId: inputArguments.conversationId,
        message: inputArguments.message,
        comparisonTurn: inputArguments.comparisonTurn,
        forceSettledAssistantActions: true,
        forceSettledAssistantBody: true
    };
    const applied = inputArguments.canonicalCorrection ? patchRenderedAssistantMessageInConversation(host, { ...patch, intent: 'idleRefresh' }) : patchRenderedAssistantMessageInConversation(host, { ...patch, intent: 'terminalFinalize' });
    return applied;
};

const postRenderSettledTerminalAssistant = (context: ChatStreamingControllerContext, result: TerminalAssistantSettlementResult, onCommitted?: () => void): void => {
    const postRenderType = resolveAssistantMutationPostRenderType({
        changed: result.changed,
        requiresPostRender: result.requiresPostRender,
        surface: 'terminalFinalize'
    });
    if (postRenderType !== null) {
        if (onCommitted === undefined) {
            context.dependencies.messageManager.postRenderRequest(result.root, postRenderType);
        } else {
            context.dependencies.messageManager.postRenderRequest(result.root, postRenderType, onCommitted);
        }
    }
};

const resolveTerminalAssistantSettlementFingerprint = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; assistantMessage: ChatMessage | null; activeConversationId: string | null }): string | null => {
    const patchPlan = resolveTerminalAssistantSettlementPlan(context, inputArguments);
    return patchPlan.assistantMessage === null ? null : resolveSettledMessageFingerprint(patchPlan.assistantMessage, patchPlan.comparisonTurn);
};

const settleTerminalAssistantMessageDom = (context: ChatStreamingControllerContext, inputArguments: { conversationId: string; assistantMessage: ChatMessage | null; activeConversationId: string | null; canonicalCorrection?: boolean; onPostRenderCommitted?: () => void }): TerminalAssistantSettlementReceipt | null => {
    try {
        const patchPlan = resolveTerminalAssistantSettlementPlan(context, inputArguments);
        if (patchPlan.assistantMessage === null) {
            return null;
        }
        context.dependencies.messageManager.invalidateMessageCache(patchPlan.assistantMessage);
        const conversation = context.dependencies.conversations.get(inputArguments.conversationId);
        if (!conversation || !isObject(conversation)) {
            return null;
        }
        const applied = settleTerminalAssistantMessage(context, {
            conversation,
            conversationId: inputArguments.conversationId,
            message: patchPlan.assistantMessage,
            comparisonTurn: patchPlan.comparisonTurn,
            canonicalCorrection: inputArguments.canonicalCorrection === true
        });
        if (applied === null) {
            return null;
        }
        reconcileStreamingSpinnerStatusSubtree(applied.root);
        context.reconcileActivityDurations?.(applied.root, inputArguments.conversationId);
        postRenderSettledTerminalAssistant(context, applied, inputArguments.onPostRenderCommitted);
        return { root: applied.root, messageDomId: applied.messageDomId, settledMarkup: applied.root.outerHTML };
    } catch (error) {
        const runtimeError = ensureError(error);
        context.errorHandler?.error?.('ChatStream', `Terminal assistant message settlement failed after stream completion for ${inputArguments.conversationId}`, runtimeError);
        return null;
    }
};

const isTerminalAssistantSettlementReceiptCurrent = (context: ChatStreamingControllerContext, receipt: TerminalAssistantSettlementReceipt): boolean => {
    const messagesArea = context.dependencies.presentation.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    if (!(messagesArea instanceof HTMLElement) || !receipt.root.isConnected) return false;
    try {
        const parts = resolveAssistantMessageParts(receipt.root);
        return (
            canSerializeSettledAssistantBody(receipt.root) &&
            receipt.root.outerHTML === receipt.settledMarkup &&
            parts?.response instanceof HTMLElement &&
            buildAssistantBodyItems(parts.response) !== null &&
            isChatMessageDomOwnedByLiveContainer({
                liveContainer: messagesArea,
                messageRoot: receipt.root,
                messageDomId: receipt.messageDomId
            })
        );
    } catch (error) {
        context.errorHandler?.debug?.('ChatStream', 'Terminal assistant settlement receipt DOM validation failed', ensureError(error));
        return false;
    }
};

export { isTerminalAssistantSettlementReceiptCurrent, resolveTerminalAssistantSettlementFingerprint, settleTerminalAssistantMessageDom };
export type { TerminalAssistantSettlementReceipt };
