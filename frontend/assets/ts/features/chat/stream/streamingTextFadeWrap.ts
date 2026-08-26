/* SoAI - Chat feature streaming text fade wrap [frontend/assets/ts/features/chat/stream/streamingTextFadeWrap.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { dom } from '@core/dom/dom.ts';

const STREAM_WORD_CLASS = 'stream-word-reveal';
const STREAM_WORD_CONTINUATION_ATTRIBUTE = 'data-stream-word-continuation';
const STREAM_WORD_CONTINUATION_SELECTOR = `[${STREAM_WORD_CONTINUATION_ATTRIBUTE}="true"]`;
const STREAM_WORD_REVEAL_ANIMATION_NAME = 'stream-word-reveal';
const INLINE_MEDIA_CARD_SELECTOR = '.chat-inline-media-card[data-inline-media-card="1"]';
const REVEAL_ELEMENT_SELECTOR = `.assistant-activity-widgets > *, .assistant-news-widget, .assistant-weather-widget, ${INLINE_MEDIA_CARD_SELECTOR}`;
const SEMANTIC_INLINE_REVEAL_SELECTOR = 'a, del, em, strong';
const SKIP_ANCESTOR_SELECTOR = `button, code, math, pre, script, style, svg, ${REVEAL_ELEMENT_SELECTOR}, .${STREAM_WORD_CLASS}, .code-block, .code-copy-btn, .katex, .katex-display, .math-block, .math-inline, .mermaid-container, .message-code-block, .ui-icon, .ui-icon-button`;

type TrailingPartialCandidate = Text | 'complete' | null;

const isInsideSkippedAncestor = (textNode: Text): boolean => {
    const parent = textNode.parentElement;
    return parent !== null && parent.closest(SKIP_ANCESTOR_SELECTOR) !== null;
};

const isSkippedElement = (element: Element): boolean => {
    return element.matches(SKIP_ANCESTOR_SELECTOR);
};

const applyRevealClassToElement = (element: Element): void => {
    if (element instanceof HTMLElement && !element.classList.contains(STREAM_WORD_CLASS)) {
        element.classList.add(STREAM_WORD_CLASS);
    }
};

const applyRevealClassToElementRoots = (root: ParentNode): void => {
    if (root instanceof Element && root.matches(REVEAL_ELEMENT_SELECTOR)) {
        applyRevealClassToElement(root);
    }
    if (!(root instanceof Element || root instanceof DocumentFragment || root instanceof Document)) {
        return;
    }
    for (const element of dom.resolveAll(REVEAL_ELEMENT_SELECTOR, root)) {
        applyRevealClassToElement(element);
    }
};

const splitTextIntoWordGroups = (text: string): ReadonlyArray<string> => {
    const parts = text.split(/(\s+)/);
    const groups: string[] = [];
    for (let index = 0; index < parts.length; index += 2) {
        const word = parts[index] ?? '';
        const whitespace = parts[index + 1] ?? '';
        const group = `${word}${whitespace}`;
        if (group.length > 0) {
            groups.push(group);
        }
    }
    return groups;
};

const appendWordGroupNode = (fragment: DocumentFragment, doc: Document, group: string): HTMLElement | null => {
    if (group.trim().length === 0) {
        fragment.appendChild(doc.createTextNode(group));
        return null;
    }
    const span = doc.createElement('span');
    span.className = STREAM_WORD_CLASS;
    span.textContent = group;
    fragment.appendChild(span);
    return span;
};

const isPureRevealSpan = (element: HTMLElement): boolean => element.tagName.toLowerCase() === 'span' && element.classList.length === 1 && element.classList.contains(STREAM_WORD_CLASS);

const unwrapRevealSpan = (element: HTMLElement): void => {
    if (element.parentNode !== null) {
        element.replaceWith(...Array.from(element.childNodes));
    }
};

const removeRevealClass = (element: HTMLElement): void => {
    element.classList.remove(STREAM_WORD_CLASS);
    if (element.classList.length === 0) {
        element.removeAttribute('class');
    }
};

const retireStreamingRevealElement = (element: HTMLElement): void => {
    const isContinuation = element.getAttribute(STREAM_WORD_CONTINUATION_ATTRIBUTE) === 'true';
    if (isContinuation) {
        removeRevealClass(element);
        return;
    }
    if (isPureRevealSpan(element)) {
        unwrapRevealSpan(element);
        return;
    }
    removeRevealClass(element);
};

const releaseStreamingContinuation = (element: HTMLElement): void => {
    element.removeAttribute(STREAM_WORD_CONTINUATION_ATTRIBUTE);
    if (!element.classList.contains(STREAM_WORD_CLASS) && element.tagName.toLowerCase() === 'span' && element.classList.length === 0) {
        unwrapRevealSpan(element);
    }
};

const releaseStreamingTextContinuation = (root: HTMLElement): void => {
    for (const marker of dom.resolveAll(STREAM_WORD_CONTINUATION_SELECTOR, root)) {
        if (marker instanceof HTMLElement) {
            releaseStreamingContinuation(marker);
        }
    }
};

const normalizeStreamingRevealTree = (root: HTMLElement): boolean => {
    let changed = false;
    const elements = [...(root.matches(`.${STREAM_WORD_CLASS}, ${STREAM_WORD_CONTINUATION_SELECTOR}`) ? [root] : []), ...dom.resolveAll(`.${STREAM_WORD_CLASS}, ${STREAM_WORD_CONTINUATION_SELECTOR}`, root).filter((element): element is HTMLElement => element instanceof HTMLElement)];
    for (const element of elements) {
        if (!element.isConnected && !root.contains(element)) {
            continue;
        }
        const pureSpan = element.tagName.toLowerCase() === 'span' && Array.from(element.classList).every((className) => className === STREAM_WORD_CLASS);
        element.removeAttribute(STREAM_WORD_CONTINUATION_ATTRIBUTE);
        if (pureSpan) {
            unwrapRevealSpan(element);
        } else {
            removeRevealClass(element);
        }
        changed = true;
    }
    return changed;
};

const markStreamingTextContinuation = (root: HTMLElement): void => {
    releaseStreamingTextContinuation(root);
    const revealElements = dom.resolveAll(`.${STREAM_WORD_CLASS}`, root);
    for (let index = revealElements.length - 1; index >= 0; index -= 1) {
        const element = revealElements[index];
        if (element instanceof HTMLElement && isPureRevealSpan(element) && element.parentElement?.closest(SKIP_ANCESTOR_SELECTOR) === null) {
            element.setAttribute(STREAM_WORD_CONTINUATION_ATTRIBUTE, 'true');
            return;
        }
    }
    const textNode = findTrailingPartialTextNode(root);
    if (textNode === null || textNode.parentNode === null) {
        return;
    }
    const marker = textNode.ownerDocument.createElement('span');
    marker.setAttribute(STREAM_WORD_CONTINUATION_ATTRIBUTE, 'true');
    textNode.replaceWith(marker);
    marker.appendChild(textNode);
};

const handleStreamingRevealAnimationCompletion = (event: AnimationEvent): void => {
    if (event.animationName !== STREAM_WORD_REVEAL_ANIMATION_NAME || !(event.target instanceof HTMLElement) || !event.target.classList.contains(STREAM_WORD_CLASS)) {
        return;
    }
    const currentTarget = event.currentTarget;
    if (!(currentTarget instanceof HTMLElement) || !currentTarget.contains(event.target)) {
        return;
    }
    retireStreamingRevealElement(event.target);
};

const armStreamingTextRevealLifecycle = (root: HTMLElement): void => {
    root.addEventListener('animationend', handleStreamingRevealAnimationCompletion);
    root.addEventListener('animationcancel', handleStreamingRevealAnimationCompletion);
};

const resolveTrailingPartialCandidate = (root: ParentNode): TrailingPartialCandidate => {
    const childNodes = root.childNodes;
    for (let index = childNodes.length - 1; index >= 0; index -= 1) {
        const child = childNodes[index];
        if (child instanceof Text) {
            if (child.data.length === 0) {
                continue;
            }
            if (child.data.trim().length === 0 || isInsideSkippedAncestor(child)) {
                return 'complete';
            }
            return child;
        }
        if (child instanceof Element) {
            if (isSkippedElement(child)) {
                return 'complete';
            }
            const candidate = resolveTrailingPartialCandidate(child);
            if (candidate !== null) {
                return candidate;
            }
            return 'complete';
        }
    }
    return null;
};

const findTrailingPartialTextNode = (root: ParentNode): Text | null => {
    const candidate = resolveTrailingPartialCandidate(root);
    return candidate instanceof Text ? candidate : null;
};

const resolveSemanticInlineRevealTarget = (root: ParentNode, textNode: Text): HTMLElement | null => {
    let current = textNode.parentElement;
    let semantic: HTMLElement | null = null;
    while (current !== null) {
        if (current.matches(SEMANTIC_INLINE_REVEAL_SELECTOR)) {
            semantic = current;
        }
        if (current === root) {
            break;
        }
        current = current.parentElement;
    }
    if (semantic === null) {
        return null;
    }
    if (root instanceof HTMLElement && !root.contains(semantic)) {
        return root;
    }
    return semantic;
};

const wrapTextNodeInFadeSpans = (textNode: Text): void => {
    const groups = splitTextIntoWordGroups(textNode.data);
    if (groups.length === 0) {
        return;
    }
    const doc = textNode.ownerDocument;
    const fragment = doc.createDocumentFragment();
    for (const group of groups) {
        appendWordGroupNode(fragment, doc, group);
    }
    textNode.replaceWith(fragment);
};

const wrapAllTextNodesInFadeSpans = (root: ParentNode, doc: Document): void => {
    applyRevealClassToElementRoots(root);
    const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const textNodes: Text[] = [];
    let currentNode: Node | null = walker.nextNode();
    while (currentNode) {
        if (currentNode instanceof Text) {
            textNodes.push(currentNode);
        }
        currentNode = walker.nextNode();
    }
    for (const textNode of textNodes) {
        if (isInsideSkippedAncestor(textNode)) {
            continue;
        }
        const semanticRevealTarget = resolveSemanticInlineRevealTarget(root, textNode);
        if (semanticRevealTarget !== null) {
            applyRevealClassToElement(semanticRevealTarget);
            continue;
        }
        wrapTextNodeInFadeSpans(textNode);
    }
};

export { appendWordGroupNode, armStreamingTextRevealLifecycle, isInsideSkippedAncestor, markStreamingTextContinuation, normalizeStreamingRevealTree, releaseStreamingContinuation, releaseStreamingTextContinuation, retireStreamingRevealElement, splitTextIntoWordGroups, STREAM_WORD_CLASS, STREAM_WORD_CONTINUATION_ATTRIBUTE, STREAM_WORD_CONTINUATION_SELECTOR };

export const applyStreamingTextFadeToElement = (element: HTMLElement): void => {
    wrapAllTextNodesInFadeSpans(element, element.ownerDocument);
    if (prefersReducedMotion(element)) {
        normalizeStreamingRevealTree(element);
    }
};
