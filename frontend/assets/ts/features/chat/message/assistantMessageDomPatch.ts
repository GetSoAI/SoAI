/* SoAI - Assistant message DOM patch application for rendered conversation messages [frontend/assets/ts/features/chat/message/assistantMessageDomPatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import { applyAssistantRenderTransaction, type AssistantRenderIntent } from '@features/chat/message/assistantRenderTransaction.ts';
import type { AssistantRenderCacheUpdate } from '@features/chat/message/assistantRenderCacheUpdate.ts';
import { isChatMessageDomOwnedByLiveContainer } from '@features/chat/message/messageDomOwnership.ts';
import { resolveMessageDomId } from '@features/chat/message/messageDomIds.ts';
import type { ChatMessageRenderModel } from '@features/chat/message/messageRenderModel.ts';
import { resolveAssistantMessageRoot } from '@features/chat/stream/streamDomCache.ts';
import { requireAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';
import { resolveAssistantVariantMessageIndex } from '@features/chat/message/assistantMessageIdentity.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import type { TrustedHtml } from '@core/security/public.ts';

interface AssistantMessageRenderPort {
    renderMessage(model: ChatMessageRenderModel): TrustedHtml;
    resolveMessageRenderPresentation(conversation: ConversationContract, message: ChatMessage, messageIndex: number): ChatMessageRenderModel['presentation'];
}

interface AssistantMessageDomPatchHost {
    optionalUI(selector: string, parent?: Element): Element | null;
    messageManager: AssistantMessageRenderPort;
    updateConversationRenderCache?: AssistantRenderCacheUpdate;
}

type AssistantMessageDomPatchResult = {
    root: HTMLElement;
    messageDomId: string;
    changed: boolean;
    requiresPostRender: boolean;
};

const resolveDefaultRenderIntent = (forceSettledAssistantActions: boolean): AssistantRenderIntent => (forceSettledAssistantActions ? 'terminalFinalize' : 'runningUpdate');

const resolveAssistantMessageIndex = (conversation: ConversationContract, message: ChatMessage): number | null => {
    if (!conversation.messages.length) {
        return null;
    }
    if (message.role !== 'assistant') {
        throw new Error('Assistant message DOM patch requires an assistant message');
    }
    const identity = requireAssistantVariantIdentity({
        assistantTurnTimestamp: message.assistantTurnAtMs,
        modelVariantIndex: message.modelVariantIndex,
        context: 'Assistant message DOM patch'
    });
    return resolveAssistantVariantMessageIndex(conversation.messages, identity);
};

const resolveAssistantMessageDomIdentity = (conversation: ConversationContract, message: ChatMessage): { domId: string; index: number } | null => {
    const index = resolveAssistantMessageIndex(conversation, message);
    if (index === null) {
        return null;
    }
    return { domId: resolveMessageDomId(message, index), index };
};

const patchRenderedAssistantMessageInConversation = (
    host: AssistantMessageDomPatchHost,
    inputArguments: {
        conversation: ConversationContract;
        conversationId: string;
        message: ChatMessage;
        comparisonTurn: ChatComparisonTurnRenderModel | null;
        forceSettledAssistantActions: boolean;
        forceSettledAssistantBody?: boolean;
        intent?: AssistantRenderIntent;
    }
): AssistantMessageDomPatchResult | null => {
    const conversationId = normalizeConversationId(inputArguments.conversationId);
    if (!conversationId) {
        return null;
    }
    const messageIdentity = resolveAssistantMessageDomIdentity(inputArguments.conversation, inputArguments.message);
    if (!messageIdentity) {
        return null;
    }
    const messagesArea = host.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    if (!(messagesArea instanceof HTMLElement)) {
        return null;
    }
    const messageRoot = resolveAssistantMessageRoot(messagesArea, messageIdentity.domId);
    if (
        !messageRoot ||
        !isChatMessageDomOwnedByLiveContainer({
            liveContainer: messagesArea,
            messageRoot,
            messageDomId: messageIdentity.domId
        })
    ) {
        return null;
    }
    const markup = host.messageManager.renderMessage({
        message: inputArguments.message,
        conversationId,
        index: messageIdentity.index,
        comparisonTurn: inputArguments.comparisonTurn,
        presentation: host.messageManager.resolveMessageRenderPresentation(inputArguments.conversation, inputArguments.message, messageIdentity.index),
        forceSettledAssistantActions: inputArguments.forceSettledAssistantActions,
        ...(inputArguments.forceSettledAssistantBody === true ? { forceSettledAssistantBody: true } : {})
    });
    const applied = applyAssistantRenderTransaction({
        existingMessageRoot: messageRoot,
        nextMarkup: markup,
        intent: inputArguments.intent ?? resolveDefaultRenderIntent(inputArguments.forceSettledAssistantActions),
        conversationId,
        messageDomId: messageIdentity.domId,
        message: inputArguments.message,
        comparisonTurn: inputArguments.comparisonTurn,
        viewportStabilityScope: 'transaction',
        ...(inputArguments.forceSettledAssistantBody === true ? { forceSettledAssistantBody: true } : {}),
        ...(typeof host.updateConversationRenderCache === 'function' ? { updateConversationRenderCache: host.updateConversationRenderCache } : {})
    });
    const appliedDomIdRaw = applied.root.getAttribute('data-id');
    const appliedDomId = appliedDomIdRaw ? appliedDomIdRaw.trim() : '';
    const resolvedDomId = appliedDomId ? appliedDomId : messageIdentity.domId;
    return {
        root: applied.root,
        messageDomId: resolvedDomId,
        changed: applied.changed,
        requiresPostRender: applied.requiresPostRender
    };
};

export { patchRenderedAssistantMessageInConversation };
export type { AssistantMessageRenderPort };
