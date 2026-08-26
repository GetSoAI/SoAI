/* SoAI - Incremental DOM patching for rich text streaming content [frontend/assets/ts/features/chat/stream/streamRichTextPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { createHtmlFragment } from '@core/dom/html.ts';
import { reconcileAssistantDom } from '@features/chat/message/assistantDomReconciler.ts';
import { collectAssistantDomState } from '@features/chat/message/assistantDomState.ts';
import { wrapStreamingTextFadeTailHtml } from '@features/chat/stream/streamingTextFadeTail.ts';
import { markStreamingTextContinuation, normalizeStreamingRevealTree, releaseStreamingTextContinuation } from '@features/chat/stream/streamingTextFadeWrap.ts';

const replacePatchedContentPreservingAssistantState = (streamText: HTMLElement, sourceNodes: ReadonlyArray<ChildNode>): void => {
    const sourceRoot = streamText.ownerDocument.createElement('div');
    sourceRoot.append(...sourceNodes);
    if (prefersReducedMotion(sourceRoot)) {
        normalizeStreamingRevealTree(sourceRoot);
    }
    releaseStreamingTextContinuation(streamText);
    const state = collectAssistantDomState(streamText);
    reconcileAssistantDom({ target: streamText, source: sourceRoot, mode: 'streamingRichText', state });
    markStreamingTextContinuation(streamText);
};

const patchRichTextContent = (streamText: HTMLElement, richHtml: string): void => {
    const revealedTailHtml = wrapStreamingTextFadeTailHtml(richHtml, streamText);
    const fragment = createHtmlFragment({ documentRef: streamText.ownerDocument, html: revealedTailHtml, context: streamText });
    const sourceNodes = Array.from(fragment.childNodes);
    replacePatchedContentPreservingAssistantState(streamText, sourceNodes);
};

export { patchRichTextContent };
