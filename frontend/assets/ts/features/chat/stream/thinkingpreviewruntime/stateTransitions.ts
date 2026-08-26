/* SoAI - Chat feature state transitions [frontend/assets/ts/features/chat/stream/thinkingpreviewruntime/stateTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stripTrailingPreviewDot, THINKING_PREVIEW_ATTRIBUTE_NAMES } from '@features/chat/message/messageview/inlineActivityText.ts';
import { clearThinkingPreviewTimers, deleteThinkingPreviewState, type ThinkingPreviewState } from '@features/chat/stream/thinkingPreviewStateStore.ts';
import { readThinkingPreviewAttribute, requireThinkingPreviewWindow } from '@features/chat/stream/thinkingpreviewruntime/dom.ts';

const resetStreamingBuffer = (state: ThinkingPreviewState): void => {
    state.pendingText = null;
    state.streamWords = null;
    state.streamWordIndex = 0;
};

const applyRenderedThinkingPreviewText = (state: ThinkingPreviewState, preview: string, options?: { syncVisibleAttribute?: boolean }): void => {
    const normalizedPreview = stripTrailingPreviewDot(preview);
    const queryElement = state.queryElement;
    const textElement = state.textElement;
    const shouldSyncAttribute = options?.syncVisibleAttribute !== false;
    if (queryElement && shouldSyncAttribute) {
        const current = queryElement.getAttribute(THINKING_PREVIEW_ATTRIBUTE_NAMES.visible);
        if (current !== normalizedPreview) {
            queryElement.setAttribute(THINKING_PREVIEW_ATTRIBUTE_NAMES.visible, normalizedPreview);
        }
    }
    state.renderedPreview = normalizedPreview;
    if (textElement) {
        if (textElement.textContent !== normalizedPreview) {
            textElement.textContent = normalizedPreview;
        }
    }
};

const applyThinkingPreviewText = (state: ThinkingPreviewState, preview: string): void => {
    applyRenderedThinkingPreviewText(state, preview);
    state.lastShownPreview = state.renderedPreview;
};

const bindThinkingPreviewState = (state: ThinkingPreviewState, queryElement: HTMLElement, textElement: HTMLElement): void => {
    state.queryElement = queryElement;
    state.textElement = textElement;
    state.view = requireThinkingPreviewWindow(queryElement);
    applyRenderedThinkingPreviewText(state, state.renderedPreview, {
        syncVisibleAttribute: state.pendingText === null && state.streamWords === null
    });
    textElement.classList.remove('inline-activity-preview-text-fading');
};

const finalizeThinkingPreviewState = (state: ThinkingPreviewState): void => {
    const queryElement = state.queryElement;
    const textElement = state.textElement;
    clearThinkingPreviewTimers(state);
    resetStreamingBuffer(state);
    if (textElement) {
        textElement.classList.remove('inline-activity-preview-text-fading');
    }
    if (queryElement) {
        const latestPreview = stripTrailingPreviewDot(readThinkingPreviewAttribute(queryElement, THINKING_PREVIEW_ATTRIBUTE_NAMES.latest));
        const visiblePreview = stripTrailingPreviewDot(readThinkingPreviewAttribute(queryElement, THINKING_PREVIEW_ATTRIBUTE_NAMES.visible));
        const finalPreview = latestPreview || state.lastShownPreview || visiblePreview;
        applyThinkingPreviewText(state, finalPreview);
    }
    deleteThinkingPreviewState(state.document, state.callId);
};

export { applyRenderedThinkingPreviewText, applyThinkingPreviewText, bindThinkingPreviewState, finalizeThinkingPreviewState, resetStreamingBuffer };
