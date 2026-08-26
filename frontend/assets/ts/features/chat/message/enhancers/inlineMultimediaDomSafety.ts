/* SoAI - Chat feature inline multimedia DOM safety [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaDomSafety.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbsoluteHttpUrl } from '@core/security/public.ts';

const STREAMING_TAIL_SELECTOR = '[data-stream-text-tail="true"]';
const INLINE_MEDIA_EXCLUDED_ANCESTORS_SELECTOR = 'pre, code, .chat-inline-media-card, .message-error, .inline-activity-details, .assistant-news-widget, .assistant-plan-widget, .assistant-weather-widget, .chat-message.user';

const isElementInOwnDocument = (node: Node): node is Element => {
    const ownerDocument = node.ownerDocument;
    const ctor = ownerDocument?.defaultView?.Element ?? null;
    return ctor !== null && node instanceof ctor;
};

const isTextInOwnDocument = (node: Node): node is Text => {
    const ownerDocument = node.ownerDocument;
    const ctor = ownerDocument?.defaultView?.Text ?? null;
    return ctor !== null && node instanceof ctor;
};

const isHTMLElementInOwnDocument = (element: Element): element is HTMLElement => {
    const ctor = element.ownerDocument.defaultView?.HTMLElement ?? null;
    return ctor !== null && element instanceof ctor;
};

const isHTMLAnchorElementInOwnDocument = (element: Element): element is HTMLAnchorElement => {
    const ctor = element.ownerDocument.defaultView?.HTMLAnchorElement ?? null;
    return ctor !== null && element instanceof ctor;
};

const isHTMLImageElementInOwnDocument = (element: Element): element is HTMLImageElement => {
    const ctor = element.ownerDocument.defaultView?.HTMLImageElement ?? null;
    return ctor !== null && element instanceof ctor;
};

const isHTMLAudioElementInOwnDocument = (element: Element): element is HTMLAudioElement => {
    const ctor = element.ownerDocument.defaultView?.HTMLAudioElement ?? null;
    return ctor !== null && element instanceof ctor;
};

const isHTMLVideoElementInOwnDocument = (element: Element): element is HTMLVideoElement => {
    const ctor = element.ownerDocument.defaultView?.HTMLVideoElement ?? null;
    return ctor !== null && element instanceof ctor;
};

const shouldSkipInlineMediaSurface = (element: Element): boolean => {
    return element.closest(INLINE_MEDIA_EXCLUDED_ANCESTORS_SELECTOR) !== null;
};

const shouldSkipInlineMediaImage = (element: Element): boolean => {
    if (!isHTMLElementInOwnDocument(element)) {
        return true;
    }
    if (element.closest(STREAMING_TAIL_SELECTOR)) {
        return true;
    }
    if (shouldSkipInlineMediaSurface(element)) {
        return true;
    }
    return false;
};

const shouldSkipInlineMediaAnchor = (element: Element): boolean => {
    if (!isHTMLElementInOwnDocument(element)) {
        return true;
    }
    if (element.closest(STREAMING_TAIL_SELECTOR)) {
        return true;
    }
    if (shouldSkipInlineMediaSurface(element)) {
        return true;
    }
    if (element.closest('[data-action]')) {
        return true;
    }
    return false;
};

const resolveEligibleInlineMediaRemoteAnchorHref = (anchor: HTMLAnchorElement): string | null => {
    if (shouldSkipInlineMediaAnchor(anchor)) {
        return null;
    }
    const href = (anchor.getAttribute('href') ?? '').trim();
    if (!isAbsoluteHttpUrl(href)) {
        return null;
    }
    const parent = anchor.parentElement;
    if (!parent || parent.textContent === null) {
        return null;
    }
    if ((anchor.textContent ?? '').trim() !== href || parent.textContent.trim() !== href) {
        return null;
    }
    return href;
};

export { INLINE_MEDIA_EXCLUDED_ANCESTORS_SELECTOR, STREAMING_TAIL_SELECTOR, isElementInOwnDocument, isHTMLAnchorElementInOwnDocument, isHTMLAudioElementInOwnDocument, isHTMLElementInOwnDocument, isHTMLImageElementInOwnDocument, isHTMLVideoElementInOwnDocument, isTextInOwnDocument, resolveEligibleInlineMediaRemoteAnchorHref, shouldSkipInlineMediaAnchor, shouldSkipInlineMediaImage, shouldSkipInlineMediaSurface };
