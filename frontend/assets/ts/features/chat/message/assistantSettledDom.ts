/* SoAI - Settled assistant DOM normalization and body serialization [frontend/assets/ts/features/chat/message/assistantSettledDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { createHtmlFragment } from '@core/dom/html.ts';
import { normalizeSerializedMarkdownTableSortState } from '@features/chat/message/assistantMarkdownTableSortState.ts';
import { hasSettledAssistantActionsChrome, normalizeSettledAssistantActionsChrome } from '@features/chat/message/assistantMessageActionsPatching.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { ASSISTANT_STREAM_TEXT_SELECTOR, collectCanonicalStreamingTextChildNodes, hasStreamingAssistantDom } from '@features/chat/message/assistantStreamingDomState.ts';
import { STREAM_SEGMENTS_ATTRIBUTE, STREAM_SEGMENTS_SELECTOR } from '@features/chat/stream/streamSegmentsMarker.ts';
import { normalizeStreamingRevealTree, STREAM_WORD_CLASS, STREAM_WORD_CONTINUATION_SELECTOR } from '@features/chat/stream/streamingTextFadeWrap.ts';

const TRANSIENT_SELECTOR = [STREAM_SEGMENTS_SELECTOR, ASSISTANT_STREAM_TEXT_SELECTOR, '[data-stream-text-settled="true"]', '[data-stream-text-tail="true"]', `.${STREAM_WORD_CLASS}`, STREAM_WORD_CONTINUATION_SELECTOR, '.fade-slide-in', '.message-action-buttons-enter'].join(',');
const TRANSIENT_CLASS_NAMES: readonly string[] = [STREAM_WORD_CLASS, 'fade-slide-in', 'message-action-buttons-enter'];
const TRANSIENT_ATTRIBUTE_NAMES: readonly string[] = [STREAM_SEGMENTS_ATTRIBUTE, 'data-stream-text', 'data-stream-text-visible', 'data-stream-text-settled', 'data-stream-text-tail'];

const replaceElementWithNodes = (element: HTMLElement, nodes: ChildNode[]): boolean => {
    const parent = element.parentNode;
    if (parent === null) {
        return false;
    }
    element.replaceWith(...nodes);
    return true;
};

const flattenStreamingText = (root: HTMLElement): boolean => {
    let changed = false;
    for (const element of dom.resolveAll(ASSISTANT_STREAM_TEXT_SELECTOR, root)) {
        if (element instanceof HTMLElement && replaceElementWithNodes(element, collectCanonicalStreamingTextChildNodes(element))) {
            changed = true;
        }
    }
    return changed;
};

const flattenStreamingSegments = (root: HTMLElement): boolean => {
    let changed = false;
    for (const element of dom.resolveAll(STREAM_SEGMENTS_SELECTOR, root)) {
        if (element instanceof HTMLElement && replaceElementWithNodes(element, Array.from(element.childNodes))) {
            changed = true;
        }
    }
    return changed;
};

const clearTransientMarkers = (root: HTMLElement): boolean => {
    let changed = false;
    const elements = [root, ...dom.resolveAll(TRANSIENT_SELECTOR, root).filter((element): element is HTMLElement => element instanceof HTMLElement)];
    for (const element of elements) {
        for (const className of TRANSIENT_CLASS_NAMES) {
            if (element.classList.contains(className)) {
                element.classList.remove(className);
                changed = true;
            }
        }
        for (const attributeName of TRANSIENT_ATTRIBUTE_NAMES) {
            if (element.hasAttribute(attributeName)) {
                element.removeAttribute(attributeName);
                changed = true;
            }
        }
    }
    return changed;
};

const normalizeSettledAssistantDom = (root: HTMLElement): boolean => {
    const textChanged = flattenStreamingText(root);
    const segmentsChanged = flattenStreamingSegments(root);
    const revealChanged = normalizeStreamingRevealTree(root);
    const markersChanged = clearTransientMarkers(root);
    const actionsChanged = normalizeSettledAssistantActionsChrome(root);
    return textChanged || segmentsChanged || revealChanged || markersChanged || actionsChanged;
};

const cloneSettledAssistantRoot = (root: HTMLElement): HTMLElement => {
    const cloned = root.cloneNode(true);
    if (!(cloned instanceof HTMLElement)) {
        throw new Error('Assistant settled DOM serialization failed to clone the assistant root.');
    }
    normalizeSettledAssistantDom(cloned);
    normalizeSerializedMarkdownTableSortState(cloned);
    return cloned;
};

const hasTransientAssistantDom = (root: HTMLElement): boolean => dom.resolve(TRANSIENT_SELECTOR, root) !== null || TRANSIENT_CLASS_NAMES.some((className) => root.classList.contains(className)) || TRANSIENT_ATTRIBUTE_NAMES.some((attributeName) => root.hasAttribute(attributeName));

const canSerializeSettledAssistantBody = (root: HTMLElement): boolean => !hasStreamingAssistantDom(root) && hasSettledAssistantActionsChrome(root);

const resolveHtmlValidationDocument = (): Document => {
    if (typeof document === 'undefined') {
        throw new Error('Assistant settled HTML validation requires a document.');
    }
    return document;
};

const isSettledAssistantHtml = (html: string, documentRef: Document = resolveHtmlValidationDocument()): boolean => {
    const container = documentRef.createElement('div');
    const fragment = createHtmlFragment({ documentRef, html, context: documentRef });
    container.appendChild(fragment);
    return !hasTransientAssistantDom(container);
};

const createSettledAssistantBodyHtml = (root: HTMLElement): string => {
    const cloned = cloneSettledAssistantRoot(root);
    if (hasTransientAssistantDom(cloned)) {
        throw new Error('Assistant settled DOM serialization contains transient streaming or animation DOM.');
    }
    const parts = resolveAssistantMessageParts(cloned);
    if (!parts?.response) {
        throw new Error('Assistant settled DOM serialization requires a canonical response root.');
    }
    const bodyHtml = parts.response.innerHTML;
    if (!isSettledAssistantHtml(bodyHtml, root.ownerDocument)) {
        throw new Error('Assistant settled body serialization contains transient markup.');
    }
    return bodyHtml;
};

export { canSerializeSettledAssistantBody, createSettledAssistantBodyHtml, hasStreamingAssistantDom, isSettledAssistantHtml, normalizeSettledAssistantDom };
