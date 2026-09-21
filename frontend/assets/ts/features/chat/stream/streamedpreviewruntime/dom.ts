/* SoAI - Chat feature streamed preview runtime DOM contracts [frontend/assets/ts/features/chat/stream/streamedpreviewruntime/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isHTMLElement } from '@core/typeGuards.ts';
import { resolveMessageDomIdFromElement } from '@features/chat/message/messageDomIds.ts';
import { STREAMED_PREVIEW_ATTRIBUTE_NAMES } from '@features/chat/message/messageview/inlineActivityText.ts';
import { COLLAPSED_LOADING_SUMMARY_SELECTOR } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';

const STREAMED_PREVIEW_SELECTOR = `.inline-activity-preview[${STREAMED_PREVIEW_ATTRIBUTE_NAMES.root}="true"]`;
const THINKING_PREVIEW_OWNER_SELECTOR = '.inline-activity-type-thinking[data-call-id]';
const STREAMED_PREVIEW_OWNER_SELECTOR = `${THINKING_PREVIEW_OWNER_SELECTOR}, ${COLLAPSED_LOADING_SUMMARY_SELECTOR}`;

const requireStreamedPreviewTextElement = (queryElement: HTMLElement): HTMLElement => {
    let candidate: HTMLElement | null = null;
    for (const child of Array.from(queryElement.children)) {
        if (child instanceof HTMLElement && child.classList.contains('inline-activity-preview-text')) {
            candidate = child;
            break;
        }
    }
    if (!isHTMLElement(candidate)) {
        throw new Error('Streamed preview query is missing required text element.');
    }
    return candidate;
};

const requireStreamedPreviewKey = (queryElement: HTMLElement): string => {
    const owner = queryElement.closest(STREAMED_PREVIEW_OWNER_SELECTOR);
    if (!isHTMLElement(owner)) {
        throw new Error('Streamed preview query is missing owning activity.');
    }
    if (owner.matches(COLLAPSED_LOADING_SUMMARY_SELECTOR)) {
        const messageDomId = resolveMessageDomIdFromElement(owner);
        if (messageDomId === null) {
            throw new Error('Streamed preview query is missing message id.');
        }
        return `loading:${messageDomId}`;
    }
    const callId = owner.getAttribute('data-call-id');
    if (callId === null || !callId.trim()) {
        throw new Error('Streamed preview query is missing call id.');
    }
    return `thinking:${callId.trim()}`;
};

const readStreamedPreviewAttribute = (queryElement: HTMLElement, attributeName: string): string => {
    const value = queryElement.getAttribute(attributeName);
    return value === null ? '' : value;
};

const readStreamedPreviewStatus = (queryElement: HTMLElement): 'running' | 'completed' | 'cancelled' | 'error' => {
    const status = readStreamedPreviewAttribute(queryElement, STREAMED_PREVIEW_ATTRIBUTE_NAMES.status);
    if (status === 'running' || status === 'completed' || status === 'cancelled' || status === 'error') {
        return status;
    }
    throw new Error('Streamed preview query has invalid status.');
};

const requireStreamedPreviewWindow = (queryElement: HTMLElement): Window => {
    const view = queryElement.ownerDocument.defaultView;
    if (!view) {
        throw new Error('Streamed preview query is missing window context.');
    }
    return view;
};

const resolveStreamedPreviewElement = (activity: HTMLElement): HTMLElement | null => {
    for (const child of Array.from(activity.children)) {
        if (!(child instanceof HTMLElement) || !child.classList.contains('inline-activity-header')) {
            continue;
        }
        for (const headerChild of Array.from(child.children)) {
            if (headerChild instanceof HTMLElement && headerChild.classList.contains('inline-activity-preview') && headerChild.getAttribute(STREAMED_PREVIEW_ATTRIBUTE_NAMES.root) === 'true') {
                return headerChild;
            }
        }
    }
    return null;
};

export { STREAMED_PREVIEW_OWNER_SELECTOR, STREAMED_PREVIEW_SELECTOR, readStreamedPreviewAttribute, readStreamedPreviewStatus, requireStreamedPreviewKey, requireStreamedPreviewTextElement, requireStreamedPreviewWindow, resolveStreamedPreviewElement };
