/* SoAI - Inline multimedia preparation for chat message post-render effects [frontend/assets/ts/features/chat/message/postrender/inlineMultimediaPostRender.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { ChatInlineMultimediaEnhancer } from '@features/chat/message/enhancers/ChatInlineMultimediaEnhancer.ts';
import { renderDisabledReferenceToken } from '@features/chat/message/enhancers/inlineMultimediaDisabledReferences.ts';
import { MAX_DISABLED_PREVIEW_ITEMS, createInlineMultimediaPreviewFeedbackRecorder, recordDisabledInlineMultimediaPreviewFeedback } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';
import { collectInlineMediaTokensInContainer, replaceInlineMediaTokensWithRenderer } from '@features/chat/message/enhancers/inlineMultimediaTokenParsing.ts';
import { containsRawInlinePreviewToken, mayContainDisabledInlineMultimediaReferences, mayContainEnabledInlineMultimediaWork } from '@features/chat/message/enhancers/inlineMultimediaWorkDetection.ts';
import { classifyChatPostRenderCapabilitiesFromDom, type ChatPostRenderCapabilities } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';

const resolveStreamingTextPostRenderCapabilities = (container: HTMLElement): ChatPostRenderCapabilities => {
    const capabilities = new Set(classifyChatPostRenderCapabilitiesFromDom(container));
    if (container.ownerDocument.defaultView !== null && containsRawInlinePreviewToken(container)) {
        capabilities.add('inline-multimedia');
    }
    return capabilities;
};

const prepareInlineMultimediaForPostRender = (inputArguments: { container: HTMLElement; assistantMessage: ChatMessage | null; enhancer: ChatInlineMultimediaEnhancer; previewsEnabled: boolean }): void => {
    if (inputArguments.previewsEnabled) {
        const allowImplicitRemoteUrlCards = inputArguments.assistantMessage === null;
        if (!mayContainEnabledInlineMultimediaWork(inputArguments.container, allowImplicitRemoteUrlCards)) {
            return;
        }
        const feedbackRecorder = createInlineMultimediaPreviewFeedbackRecorder(inputArguments.assistantMessage);
        inputArguments.enhancer.prime(inputArguments.container, feedbackRecorder, {
            allowImplicitRemoteUrlCards
        });
        return;
    }
    if (!mayContainDisabledInlineMultimediaReferences(inputArguments.container)) {
        return;
    }
    const disabledPreviewTokens = inputArguments.assistantMessage ? collectInlineMediaTokensInContainer(inputArguments.container, { maxTokens: MAX_DISABLED_PREVIEW_ITEMS }) : null;
    replaceInlineMediaTokensWithRenderer(inputArguments.container, {
        includeStreamingTail: false,
        maxTokens: null,
        requireConnectedNodes: true,
        renderToken: renderDisabledReferenceToken
    });
    if (inputArguments.assistantMessage !== null) {
        recordDisabledInlineMultimediaPreviewFeedback(inputArguments.assistantMessage, inputArguments.container, disabledPreviewTokens);
    }
};

export { prepareInlineMultimediaForPostRender, resolveStreamingTextPostRenderCapabilities };
