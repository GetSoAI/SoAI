/* SoAI - Chat feature message post render flush [frontend/assets/ts/features/chat/message/postrender/chatMessagePostRenderFlush.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { ChatInlineMultimediaEnhancer } from '@features/chat/message/enhancers/ChatInlineMultimediaEnhancer.ts';
import { syncAssistantBodyCacheFromDom } from '@features/chat/message/postrender/assistantBodyCacheSync.ts';
import { prepareChatMessageImageLifecycles } from '@features/chat/attachments/chatImageLoadLifecycle.ts';
import { runChatMessagePostRenderEffects } from '@features/chat/message/postrender/chatMessagePostRenderEffects.ts';
import { applyKeyedScrollableState, readKeyedScrollableState } from '@features/chat/stream/streamScrollableState.ts';
import { hasChatPostRenderCapability, type ChatPostRenderCapabilities } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';
import type { ChatPostRenderContainerKey, ChatQueuedPostRenderMode } from '@features/chat/message/types.ts';

interface QueuedChatMessagePostRenderArguments {
    node: HTMLElement;
    renderKey: ChatPostRenderContainerKey;
    syntaxHighlighter: SyntaxHighlighter;
    inlineMultimediaEnhancer: ChatInlineMultimediaEnhancer;
    assistantMessage: ChatMessage | null;
    notifyDomChanged: () => void;
    inlineMultimediaPreviewsEnabled: boolean;
    increasePendingAsyncLayoutWork: () => void;
    decreasePendingAsyncLayoutWork: () => void;
    storePreRenderedAssistantBodyHtml: (message: ChatMessage, html: string) => void;
    capabilities: ChatPostRenderCapabilities | null;
    mode: ChatQueuedPostRenderMode;
    isExecutionCurrent: () => boolean;
    imageLifecyclePrepared: boolean;
}

const runQueuedChatMessagePostRenderEffects = (inputArguments: QueuedChatMessagePostRenderArguments): void => {
    const scrollState = inputArguments.mode === 'initialConversation' ? null : readKeyedScrollableState(inputArguments.node);
    if (!inputArguments.imageLifecyclePrepared && hasChatPostRenderCapability(inputArguments.capabilities, 'image-lifecycle')) prepareChatMessageImageLifecycles(inputArguments.node, () => inputArguments.notifyDomChanged());
    runChatMessagePostRenderEffects({
        node: inputArguments.node,
        syntaxHighlighter: inputArguments.syntaxHighlighter,
        inlineMultimediaEnhancer: inputArguments.inlineMultimediaEnhancer,
        assistantMessage: inputArguments.assistantMessage,
        conversationId: inputArguments.renderKey.conversationId ?? '',
        inlineMultimediaPreviewsEnabled: inputArguments.inlineMultimediaPreviewsEnabled,
        increasePendingAsyncLayoutWork: inputArguments.increasePendingAsyncLayoutWork,
        decreasePendingAsyncLayoutWork: inputArguments.decreasePendingAsyncLayoutWork,
        syncAssistantBodyCache: (target) =>
            syncAssistantBodyCacheFromDom({
                container: target,
                assistantMessage: inputArguments.assistantMessage,
                storePreRenderedAssistantBodyHtml: (message, html) => inputArguments.storePreRenderedAssistantBodyHtml(message, html)
            }),
        capabilities: inputArguments.capabilities,
        isExecutionCurrent: inputArguments.isExecutionCurrent
    });
    if (scrollState !== null) {
        applyKeyedScrollableState(inputArguments.node, scrollState);
    }
};

export { runQueuedChatMessagePostRenderEffects };
export type { QueuedChatMessagePostRenderArguments };
