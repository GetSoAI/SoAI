/* SoAI - Chat feature state transitions [frontend/assets/ts/features/chat/stream/streamedpreviewruntime/stateTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stripTrailingPreviewDot, STREAMED_PREVIEW_ATTRIBUTE_NAMES } from '@features/chat/message/messageview/inlineActivityText.ts';
import { clearStreamedPreviewTimers, deleteStreamedPreviewState, type StreamedPreviewState } from '@features/chat/stream/streamedPreviewStateStore.ts';
import { readStreamedPreviewAttribute, requireStreamedPreviewWindow } from '@features/chat/stream/streamedpreviewruntime/dom.ts';

const resetStreamingBuffer = (state: StreamedPreviewState): void => {
    state.pendingText = null;
    state.streamWords = null;
    state.streamWordIndex = 0;
};

const applyRenderedStreamedPreviewText = (state: StreamedPreviewState, preview: string, options?: { syncVisibleAttribute?: boolean }): void => {
    const normalizedPreview = stripTrailingPreviewDot(preview);
    const queryElement = state.queryElement;
    const textElement = state.textElement;
    const shouldSyncAttribute = options?.syncVisibleAttribute !== false;
    if (queryElement && shouldSyncAttribute) {
        const current = queryElement.getAttribute(STREAMED_PREVIEW_ATTRIBUTE_NAMES.visible);
        if (current !== normalizedPreview) {
            queryElement.setAttribute(STREAMED_PREVIEW_ATTRIBUTE_NAMES.visible, normalizedPreview);
        }
    }
    state.renderedPreview = normalizedPreview;
    if (textElement) {
        if (textElement.textContent !== normalizedPreview) {
            textElement.textContent = normalizedPreview;
        }
    }
};

const applyStreamedPreviewText = (state: StreamedPreviewState, preview: string): void => {
    applyRenderedStreamedPreviewText(state, preview);
    state.lastShownPreview = state.renderedPreview;
};

const bindStreamedPreviewState = (state: StreamedPreviewState, queryElement: HTMLElement, textElement: HTMLElement): void => {
    state.queryElement = queryElement;
    state.textElement = textElement;
    state.view = requireStreamedPreviewWindow(queryElement);
    applyRenderedStreamedPreviewText(state, state.renderedPreview, {
        syncVisibleAttribute: state.pendingText === null && state.streamWords === null
    });
    textElement.classList.remove('inline-activity-preview-text-fading');
};

const finalizeStreamedPreviewState = (state: StreamedPreviewState): void => {
    const queryElement = state.queryElement;
    const textElement = state.textElement;
    clearStreamedPreviewTimers(state);
    resetStreamingBuffer(state);
    if (textElement) {
        textElement.classList.remove('inline-activity-preview-text-fading');
    }
    if (queryElement) {
        const latestPreview = stripTrailingPreviewDot(readStreamedPreviewAttribute(queryElement, STREAMED_PREVIEW_ATTRIBUTE_NAMES.latest));
        const visiblePreview = stripTrailingPreviewDot(readStreamedPreviewAttribute(queryElement, STREAMED_PREVIEW_ATTRIBUTE_NAMES.visible));
        const finalPreview = latestPreview || state.lastShownPreview || visiblePreview;
        applyStreamedPreviewText(state, finalPreview);
    }
    deleteStreamedPreviewState(state.document, state.key);
};

export { applyRenderedStreamedPreviewText, applyStreamedPreviewText, bindStreamedPreviewState, finalizeStreamedPreviewState, resetStreamingBuffer };
