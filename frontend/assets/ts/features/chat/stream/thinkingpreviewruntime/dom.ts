/* SoAI - Chat feature thinking preview runtime DOM contracts [frontend/assets/ts/features/chat/stream/thinkingpreviewruntime/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isHTMLElement } from '@core/typeGuards.ts';
import { THINKING_PREVIEW_ATTRIBUTE_NAMES } from '@features/chat/message/messageview/inlineActivityText.ts';

const THINKING_PREVIEW_SELECTOR = `.inline-activity-type-thinking .inline-activity-preview[${THINKING_PREVIEW_ATTRIBUTE_NAMES.root}="true"]`;

const requireThinkingPreviewTextElement = (queryElement: HTMLElement): HTMLElement => {
    let candidate: HTMLElement | null = null;
    for (const child of Array.from(queryElement.children)) {
        if (child instanceof HTMLElement && child.classList.contains('inline-activity-preview-text')) {
            candidate = child;
            break;
        }
    }
    if (!isHTMLElement(candidate)) {
        throw new Error('Thinking preview query is missing required text element.');
    }
    return candidate;
};

const requireThinkingPreviewCallId = (queryElement: HTMLElement): string => {
    const activity = queryElement.closest('.inline-activity-type-thinking[data-call-id]');
    if (!isHTMLElement(activity)) {
        throw new Error('Thinking preview query is missing owning activity.');
    }
    const callId = activity.getAttribute('data-call-id');
    if (callId === null || !callId.trim()) {
        throw new Error('Thinking preview query is missing call id.');
    }
    return callId.trim();
};

const readThinkingPreviewAttribute = (queryElement: HTMLElement, attributeName: string): string => {
    const value = queryElement.getAttribute(attributeName);
    return value === null ? '' : value;
};

const readThinkingPreviewStatus = (queryElement: HTMLElement): 'running' | 'completed' | 'cancelled' | 'error' => {
    const status = readThinkingPreviewAttribute(queryElement, THINKING_PREVIEW_ATTRIBUTE_NAMES.status);
    if (status === 'running' || status === 'completed' || status === 'cancelled' || status === 'error') {
        return status;
    }
    throw new Error('Thinking preview query has invalid status.');
};

const requireThinkingPreviewWindow = (queryElement: HTMLElement): Window => {
    const view = queryElement.ownerDocument.defaultView;
    if (!view) {
        throw new Error('Thinking preview query is missing window context.');
    }
    return view;
};

const resolveThinkingPreviewElement = (activity: HTMLElement): HTMLElement | null => {
    for (const child of Array.from(activity.children)) {
        if (!(child instanceof HTMLElement) || !child.classList.contains('inline-activity-header')) {
            continue;
        }
        for (const headerChild of Array.from(child.children)) {
            if (headerChild instanceof HTMLElement && headerChild.classList.contains('inline-activity-preview') && headerChild.getAttribute(THINKING_PREVIEW_ATTRIBUTE_NAMES.root) === 'true') {
                return headerChild;
            }
        }
    }
    return null;
};

export { THINKING_PREVIEW_SELECTOR, readThinkingPreviewAttribute, readThinkingPreviewStatus, requireThinkingPreviewCallId, requireThinkingPreviewTextElement, requireThinkingPreviewWindow, resolveThinkingPreviewElement };
