/* SoAI - Inline continuation patching for streaming rich text tails [frontend/assets/ts/features/chat/stream/streamRichTextTailContinuation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAll } from '@core/dom/dom.ts';
import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { appendWordGroupNode, releaseStreamingContinuation, retireStreamingRevealElement, splitTextIntoWordGroups, STREAM_WORD_CONTINUATION_ATTRIBUTE, STREAM_WORD_CONTINUATION_SELECTOR } from '@features/chat/stream/streamingTextFadeWrap.ts';

const STREAMING_TAIL_ATTRIBUTE = 'data-stream-text-tail';
const TAIL_OWNER_SELECTOR = 'a, img, pre, code, .message-code-block, .markdown-table-scroll, table, .mermaid-container, .chat-inline-media-card[data-inline-media-card="1"]';
const STREAMING_TAIL_SELECTOR = `[${STREAMING_TAIL_ATTRIBUTE}="true"]`;

type StreamingPlainTextTailPatchResult = {
    patched: boolean;
    updated: boolean;
};

const isUnsafeContinuationTail = (element: HTMLElement): boolean => {
    if (element.matches(TAIL_OWNER_SELECTOR)) {
        return true;
    }
    return element.closest(TAIL_OWNER_SELECTOR) !== null;
};

const collectTailMarkers = (root: HTMLElement): HTMLElement[] => {
    const markers: HTMLElement[] = [];
    for (const candidate of resolveAll(STREAM_WORD_CONTINUATION_SELECTOR, root)) {
        if (candidate instanceof HTMLElement) {
            markers.push(candidate);
        }
    }
    return markers;
};

const resolveInlineContinuationTail = (settled: HTMLElement): HTMLElement | null => {
    const markers = collectTailMarkers(settled);
    if (markers.length !== 1) {
        return null;
    }
    const marker = markers[0];
    return marker?.tagName.toLowerCase() === 'span' && !isUnsafeContinuationTail(marker) ? marker : null;
};

const appendStreamingTailText = (target: HTMLElement, appendText: string): void => {
    const parent = target.parentNode;
    if (parent === null) {
        throw new Error('Streaming text continuation target must be attached');
    }
    const groups = splitTextIntoWordGroups(appendText);
    let groupIndex = 0;
    if (!/\s$/u.test(target.textContent ?? '') && groups.length > 0) {
        const continuation = groups[0] ?? '';
        const trailingNode = target.lastChild;
        if (trailingNode instanceof Text) {
            trailingNode.appendData(continuation);
        } else {
            target.appendChild(target.ownerDocument.createTextNode(continuation));
        }
        groupIndex = 1;
    }
    const fragment = target.ownerDocument.createDocumentFragment();
    const appendedRevealElements: HTMLElement[] = [];
    let nextContinuation: HTMLElement | null = null;
    for (; groupIndex < groups.length; groupIndex += 1) {
        const appended = appendWordGroupNode(fragment, target.ownerDocument, groups[groupIndex] ?? '');
        if (appended !== null) {
            appendedRevealElements.push(appended);
            nextContinuation = appended;
        }
    }
    parent.appendChild(fragment);
    if (nextContinuation !== null) {
        nextContinuation.setAttribute(STREAM_WORD_CONTINUATION_ATTRIBUTE, 'true');
        if (prefersReducedMotion(nextContinuation)) {
            for (const appendedRevealElement of appendedRevealElements) {
                retireStreamingRevealElement(appendedRevealElement);
            }
        }
        releaseStreamingContinuation(target);
    }
};

const patchStreamingPlainTextContinuation = (inputArguments: { tail: HTMLElement; appendText: string }): StreamingPlainTextTailPatchResult => {
    if (!inputArguments.appendText) {
        return { patched: true, updated: false };
    }
    const continuationTail = resolveInlineContinuationTail(inputArguments.tail);
    if (continuationTail === null) {
        return { patched: false, updated: false };
    }
    appendStreamingTailText(continuationTail, inputArguments.appendText);
    return { patched: true, updated: true };
};

export { patchStreamingPlainTextContinuation, STREAMING_TAIL_ATTRIBUTE, TAIL_OWNER_SELECTOR, STREAMING_TAIL_SELECTOR };
export type { StreamingPlainTextTailPatchResult };
