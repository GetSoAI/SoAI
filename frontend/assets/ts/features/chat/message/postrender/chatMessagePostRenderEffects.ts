/* SoAI - Chat message post-render effect execution [frontend/assets/ts/features/chat/message/postrender/chatMessagePostRenderEffects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getBranding } from '@core/branding/public.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { renderAllMermaidDiagrams } from '@core/mermaidRenderer.ts';
import type { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { ChatInlineMultimediaEnhancer } from '@features/chat/message/enhancers/ChatInlineMultimediaEnhancer.ts';
import { STREAMING_TAIL_SELECTOR } from '@features/chat/message/enhancers/inlineMultimediaDomSafety.ts';
import { createInlineMultimediaPreviewFeedbackRecorder } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';
import { highlightStableChatCodeBlocks } from '@features/chat/message/syntaxHighlightPostRender.ts';
import { CHAT_BRANDING_LOGO_SELECTOR, hasChatPostRenderCapability, type ChatPostRenderCapabilities } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';

type ChatMessagePostRenderEffectArguments = {
    node: HTMLElement;
    syntaxHighlighter: SyntaxHighlighter;
    inlineMultimediaEnhancer: ChatInlineMultimediaEnhancer;
    assistantMessage: ChatMessage | null;
    conversationId: string;
    inlineMultimediaPreviewsEnabled: boolean;
    increasePendingAsyncLayoutWork: () => void;
    decreasePendingAsyncLayoutWork: () => void;
    syncAssistantBodyCache: (node: HTMLElement) => void;
    capabilities: ChatPostRenderCapabilities | null;
    isExecutionCurrent: () => boolean;
};

const runAssistantActivityWidgetBrandingPostRenderEffect = (inputArguments: ChatMessagePostRenderEffectArguments): void => {
    try {
        const logoElements = dom.resolveAll(CHAT_BRANDING_LOGO_SELECTOR, inputArguments.node).filter((element): element is HTMLImageElement => element instanceof HTMLImageElement);
        if (logoElements.length === 0) {
            return;
        }
        const branding = getBranding();
        for (const element of logoElements) {
            const logoType = element.getAttribute('data-logo-type') || 'small';
            branding.updateLogoElement(element, logoType);
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.debug('ChatMessageManager', 'Assistant activity widget branding post-render failed', runtimeError);
    }
};

const runInlineMultimediaPostRenderEffect = (inputArguments: ChatMessagePostRenderEffectArguments): void => {
    if (!inputArguments.inlineMultimediaPreviewsEnabled) {
        return;
    }
    inputArguments.increasePendingAsyncLayoutWork();
    const feedbackRecorder = createInlineMultimediaPreviewFeedbackRecorder(inputArguments.assistantMessage);
    try {
        inputArguments.inlineMultimediaEnhancer
            .enhance(inputArguments.node, inputArguments.conversationId, feedbackRecorder, {
                allowImplicitRemoteUrlCards: inputArguments.assistantMessage === null
            })
            .then(() => {
                if (inputArguments.isExecutionCurrent()) inputArguments.syncAssistantBodyCache(inputArguments.node);
            })
            .catch((error) => {
                const runtimeError = ensureError(error);
                errorHandler.debug('ChatMessageManager', 'Inline multimedia post-render failed', runtimeError);
            })
            .finally(() => {
                inputArguments.decreasePendingAsyncLayoutWork();
            });
    } catch (error) {
        inputArguments.decreasePendingAsyncLayoutWork();
        const runtimeError = ensureError(error);
        errorHandler.debug('ChatMessageManager', 'Inline multimedia post-render failed (sync)', runtimeError);
    }
};

const runMermaidPostRenderEffect = (inputArguments: ChatMessagePostRenderEffectArguments): void => {
    inputArguments.increasePendingAsyncLayoutWork();
    try {
        renderAllMermaidDiagrams(inputArguments.node)
            .catch((error) => {
                const runtimeError = ensureError(error);
                errorHandler.debug('ChatMessageManager', 'Mermaid post-render failed', runtimeError);
            })
            .finally(() => {
                inputArguments.decreasePendingAsyncLayoutWork();
            });
    } catch (error) {
        inputArguments.decreasePendingAsyncLayoutWork();
        const runtimeError = ensureError(error);
        errorHandler.debug('ChatMessageManager', 'Mermaid post-render failed (sync)', runtimeError);
    }
};

const runChatMessagePostRenderEffects = (inputArguments: ChatMessagePostRenderEffectArguments): void => {
    if (hasChatPostRenderCapability(inputArguments.capabilities, 'code')) {
        try {
            highlightStableChatCodeBlocks(inputArguments.node, inputArguments.syntaxHighlighter, STREAMING_TAIL_SELECTOR);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('ChatMessageManager', 'Syntax highlight post-render failed', runtimeError);
        }
    }
    if (hasChatPostRenderCapability(inputArguments.capabilities, 'branding')) runAssistantActivityWidgetBrandingPostRenderEffect(inputArguments);
    if (hasChatPostRenderCapability(inputArguments.capabilities, 'inline-multimedia')) runInlineMultimediaPostRenderEffect(inputArguments);
    if (hasChatPostRenderCapability(inputArguments.capabilities, 'mermaid')) runMermaidPostRenderEffect(inputArguments);
};

export { runChatMessagePostRenderEffects };
