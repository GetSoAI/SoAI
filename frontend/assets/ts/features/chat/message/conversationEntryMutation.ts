/* SoAI - Canonical conversation entry DOM mutation boundary [frontend/assets/ts/features/chat/message/conversationEntryMutation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ComparisonTurnRenderEntry, MessageRenderEntry } from '@features/chat/conversation/rendering/conversationEntries.ts';
import { resolveAssistantMutationPostRenderType } from '@features/chat/message/assistantMutationPostRenderPolicy.ts';
import { applyAssistantRenderTransaction, type AssistantRenderIntent } from '@features/chat/message/assistantRenderTransaction.ts';
import { applyChatMessageRootPatchTransaction } from '@features/chat/message/chatMessageRootPatchTransaction.ts';
import type { AssistantViewportStabilityScope } from '@features/chat/message/assistantViewportStability.ts';
import { applyComparisonTurnEntryMutation } from '@features/chat/message/comparisonTurnEntryMutation.ts';
import { applyChatMessageEnterAnimation } from '@features/chat/message/messageMotion.ts';
import { parseRenderedMarkupRoot } from '@features/chat/message/renderedMarkupRoot.ts';
import type { ChatPostRenderRequestType } from '@features/chat/message/types.ts';
import type { TrustedHtml } from '@core/security/public.ts';

type ConversationEntryPostRenderRequest = {
    root: HTMLElement;
    type: ChatPostRenderRequestType;
};

type InsertConversationEntryMutation = {
    intent: 'insert';
    documentRef: Document;
    nextMarkup: TrustedHtml;
    messageDomId: string;
    animate: boolean;
};

type RefreshConversationEntryMutation = {
    intent: 'refresh';
    existingRoot: HTMLElement;
    nextMarkup: TrustedHtml;
    entry: MessageRenderEntry;
    assistantRenderIntent: Extract<AssistantRenderIntent, 'runningUpdate' | 'idleRefresh'>;
    viewportStabilityScope: AssistantViewportStabilityScope;
};

type StreamConversationEntryMutation = {
    intent: 'streamUpdate';
    existingRoot: HTMLElement;
    nextMarkup: TrustedHtml;
    entry: MessageRenderEntry;
    viewportStabilityScope: AssistantViewportStabilityScope;
};

type ComparisonConversationEntryMutation = {
    intent: 'comparisonUpdate';
    existingRoot: HTMLElement;
    nextMarkup: TrustedHtml;
    entry: ComparisonTurnRenderEntry;
    isCurrentStreaming: boolean;
    viewportStabilityScope: AssistantViewportStabilityScope;
};

type ReplaceConversationEntryMutation = {
    intent: 'replace';
    existingRoot: HTMLElement;
    nextMarkup: TrustedHtml;
    messageDomId: string;
};

type ConversationEntryMutation = InsertConversationEntryMutation | RefreshConversationEntryMutation | StreamConversationEntryMutation | ComparisonConversationEntryMutation | ReplaceConversationEntryMutation;

type ConversationEntryMutationResult = {
    root: HTMLElement;
    changed: boolean;
    postRenderRequests: ConversationEntryPostRenderRequest[];
};

const applyAssistantEntryMutation = (inputArguments: RefreshConversationEntryMutation | StreamConversationEntryMutation): ConversationEntryMutationResult => {
    const isStreamUpdate = inputArguments.intent === 'streamUpdate';
    const applied = applyAssistantRenderTransaction({
        existingMessageRoot: inputArguments.existingRoot,
        nextMarkup: inputArguments.nextMarkup,
        intent: isStreamUpdate ? 'streamingChrome' : inputArguments.assistantRenderIntent,
        messageDomId: inputArguments.entry.domId,
        message: inputArguments.entry.message,
        comparisonTurn: inputArguments.entry.comparisonTurn,
        viewportStabilityScope: inputArguments.viewportStabilityScope
    });
    const postRenderType = isStreamUpdate
        ? null
        : resolveAssistantMutationPostRenderType({
              changed: applied.changed,
              requiresPostRender: applied.requiresPostRender,
              surface: 'currentConversationRefresh'
          });
    return {
        root: applied.root,
        changed: applied.changed,
        postRenderRequests: postRenderType === null ? [] : [{ root: applied.root, type: postRenderType }]
    };
};

const applyConversationEntryMutation = (inputArguments: ConversationEntryMutation): ConversationEntryMutationResult => {
    if (inputArguments.intent === 'insert') {
        const createdRoot = parseRenderedMarkupRoot({
            documentRef: inputArguments.documentRef,
            nextMarkup: inputArguments.nextMarkup,
            context: inputArguments.documentRef,
            failureMessage: 'Chat conversation entry insertion failed to parse rendered markup.'
        });
        if (!createdRoot.classList.contains('chat-message') && !createdRoot.classList.contains('chat-comparison-turn')) {
            throw new Error('Chat conversation entry insertion requires a canonical entry root.');
        }
        if (createdRoot.getAttribute('data-id') !== inputArguments.messageDomId) {
            createdRoot.setAttribute('data-id', inputArguments.messageDomId);
        }
        if (inputArguments.animate) {
            applyChatMessageEnterAnimation(createdRoot);
        }
        return {
            root: createdRoot,
            changed: true,
            postRenderRequests: [{ root: createdRoot, type: 'canonicalFull' }]
        };
    }
    if (inputArguments.intent === 'streamUpdate' || inputArguments.intent === 'refresh') {
        return applyAssistantEntryMutation(inputArguments);
    }
    if (inputArguments.intent === 'comparisonUpdate') {
        const applied = applyComparisonTurnEntryMutation(inputArguments);
        return {
            root: inputArguments.existingRoot,
            changed: applied.changed,
            postRenderRequests: applied.postRenderRequests
        };
    }
    const patched = applyChatMessageRootPatchTransaction({
        existingRoot: inputArguments.existingRoot,
        nextMarkup: inputArguments.nextMarkup,
        messageDomId: inputArguments.messageDomId
    });
    return {
        root: patched.root,
        changed: patched.changed,
        postRenderRequests: patched.requiresPostRender ? [{ root: patched.root, type: 'canonicalFull' }] : []
    };
};

export { applyConversationEntryMutation };
