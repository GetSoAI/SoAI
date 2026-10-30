/* SoAI - Eligible single-line chat selection for conversation find [frontend/assets/ts/features/chat/conversationfind/selectionPrefill.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutRectangles } from '@core/layout/elementGeometry.ts';
import { unicodeCodePointLength } from '@core/primitives/text.ts';
import { chatSearchTextTraversalPolicy, presentedChatSearchTextTraversalPolicy } from '@features/chat/message/searchTextPolicy.ts';

const captureConversationFindPrefill = (root: HTMLElement): string | null => {
    const selection = root.ownerDocument.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount !== 1) return null;
    const range = selection.getRangeAt(0);
    const start = range.startContainer instanceof Element ? range.startContainer : range.startContainer.parentElement;
    const end = range.endContainer instanceof Element ? range.endContainer : range.endContainer.parentElement;
    const body = start?.closest('.chat-message .message-text');
    if (!body || body !== end?.closest('.chat-message .message-text') || !root.contains(body) || body.closest('[inert], [hidden], .u-hidden, .is-editing')) return null;
    const text = range.toString();
    if (!text || text.length > 400 || /[\r\n]/.test(text) || unicodeCodePointLength(text) > 200) return null;
    for (const endpoint of [start, end]) {
        for (let ancestor = endpoint; ancestor; ancestor = ancestor.parentElement) {
            if (presentedChatSearchTextTraversalPolicy(ancestor) === 'exclude') return null;
            if (ancestor === body) break;
        }
    }
    const walker = root.ownerDocument.createTreeWalker(body, NodeFilter.SHOW_ELEMENT, { acceptNode: (node) => (range.intersectsNode(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT) });
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (node instanceof Element && presentedChatSearchTextTraversalPolicy(node) === 'exclude') return null;
    }
    const fragment = range.cloneContents();
    const fragments = root.ownerDocument.createTreeWalker(fragment, NodeFilter.SHOW_ELEMENT);
    let boundaries = 0;
    for (let node = fragments.nextNode(); node; node = fragments.nextNode()) {
        if (node instanceof Element && chatSearchTextTraversalPolicy(node) === 'boundary') {
            boundaries += 1;
            if (boundaries > 1 || node.matches('br,hr')) return null;
        }
    }
    if (typeof range.getClientRects === 'function') {
        const rectangles = measureLayoutRectangles(range).filter((rectangle) => rectangle.width > 0 && rectangle.height > 0);
        const first = rectangles[0];
        if (!first || rectangles.some((rectangle) => rectangle.top >= first.bottom || rectangle.bottom <= first.top)) return null;
    }
    return text;
};

export { captureConversationFindPrefill };
