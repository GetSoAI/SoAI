/* SoAI - Diff-aware streaming text fade tail wrapping [frontend/assets/ts/features/chat/stream/streamingTextFadeTail.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHtmlFragment } from '@core/dom/html.ts';
import { appendWordGroupNode, isInsideSkippedAncestor, splitTextIntoWordGroups } from '@features/chat/stream/streamingTextFadeWrap.ts';

const collectFadeTailTextNodes = (root: ParentNode, doc: Document): Text[] => {
    const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes: Text[] = [];
    let currentNode: Node | null = walker.nextNode();
    while (currentNode !== null) {
        if (currentNode instanceof Text) {
            nodes.push(currentNode);
        }
        currentNode = walker.nextNode();
    }
    return nodes;
};

const resolveCommonWordBoundary = (existingText: string, nextText: string): number => {
    const limit = Math.min(existingText.length, nextText.length);
    let common = 0;
    while (common < limit && existingText.charCodeAt(common) === nextText.charCodeAt(common)) {
        common += 1;
    }
    if (common === nextText.length || (common === existingText.length && /\s/u.test(nextText.charAt(common)))) {
        return common;
    }
    let boundary = common;
    while (boundary > 0 && !/\s/u.test(nextText.charAt(boundary - 1))) {
        boundary -= 1;
    }
    return boundary;
};

const wrapTextNodeTailRange = (textNode: Text, localBoundary: number, doc: Document): void => {
    const data = textNode.data;
    const groups = splitTextIntoWordGroups(data.slice(localBoundary));
    if (groups.length === 0) {
        return;
    }
    const fragment = doc.createDocumentFragment();
    const prefix = data.slice(0, localBoundary);
    if (prefix.length > 0) {
        fragment.appendChild(doc.createTextNode(prefix));
    }
    for (const group of groups) {
        appendWordGroupNode(fragment, doc, group);
    }
    textNode.replaceWith(fragment);
};

const wrapFragmentTailFromBoundary = (root: ParentNode, doc: Document, boundary: number): void => {
    let offset = 0;
    for (const textNode of collectFadeTailTextNodes(root, doc)) {
        const start = offset;
        offset += textNode.data.length;
        if (offset <= boundary) {
            continue;
        }
        if (isInsideSkippedAncestor(textNode)) {
            continue;
        }
        wrapTextNodeTailRange(textNode, Math.max(0, boundary - start), doc);
    }
};

export const wrapStreamingTextFadeTailHtml = (html: string, existingTextRoot: Element): string => {
    if (!html) {
        return html;
    }
    const doc = existingTextRoot.ownerDocument;
    const fragment = createHtmlFragment({ documentRef: doc, html, context: existingTextRoot });
    const serializer = doc.createElement('div');
    serializer.appendChild(fragment);
    const boundary = resolveCommonWordBoundary(existingTextRoot.textContent ?? '', serializer.textContent ?? '');
    wrapFragmentTailFromBoundary(serializer, doc, boundary);
    return serializer.innerHTML;
};
