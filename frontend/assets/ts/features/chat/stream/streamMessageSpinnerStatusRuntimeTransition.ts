/* SoAI - Chat feature stream message spinner status runtime transition [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { startFadingTextSwap } from '@features/chat/stream/fadingTextScheduler.ts';
import { type SpinnerStatusState, clearStateTimers, getRuntimeStateByMessageId, removeRuntimeStateByMessageId } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { hasActiveMessageActionButton } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';

export const FADING_CLASS = 'message-streaming-status-label-text-fading';
export const VISIBILITY_FADING_CLASS = 'message-streaming-status-visibility-fading';
export const FADE_DURATION_MS = 160;

const MAX_STATUS_TEXT_LENGTH = 1000;
const STATUS_TEXT_CONTINUATION_SUFFIX = '...';
const TEXT_BODY_PREVIOUS_VALUE_ATTRIBUTE = 'data-stream-spinner-previous-text-value';
const TEXT_BODY_CONTENT_ATTRIBUTE = 'data-stream-spinner-text-body-content';
const TEXT_BODY_CONTENT_CLASS_NAME = 'message-streaming-status-label-text-body';

const normalizeSpinnerStatusText = (value: string): string => {
    const trimmed = value.trim();
    if (trimmed.length > MAX_STATUS_TEXT_LENGTH) {
        return trimmed.slice(0, MAX_STATUS_TEXT_LENGTH).trimEnd();
    }
    return trimmed;
};

const applyTooltipAttributes = (element: HTMLElement, text: string): void => {
    const value = text.trim();
    if (!value) {
        setTooltipText(element, '');
        element.removeAttribute('aria-label');
        return;
    }
    setTooltipText(element, value);
    element.setAttribute('aria-label', value);
};

const clearSpinnerStatusRuntimeText = (statusElement: HTMLElement, labelElement: HTMLElement, textElement: HTMLElement, actionsElement: HTMLElement): boolean => {
    const hadTextContent = textElement.textContent !== '';
    const hadTextValue = textElement.getAttribute('data-stream-spinner-text-value') !== '';
    const hadPreviousTextValue = textElement.hasAttribute(TEXT_BODY_PREVIOUS_VALUE_ATTRIBUTE);
    textElement.textContent = '';
    textElement.setAttribute('data-stream-spinner-text-value', '');
    textElement.removeAttribute(TEXT_BODY_PREVIOUS_VALUE_ATTRIBUTE);
    applyTooltipAttributes(labelElement, '');
    applyTooltipAttributes(statusElement, '');
    applyTooltipAttributes(actionsElement, '');
    return hadTextContent || hadTextValue || hadPreviousTextValue;
};

const resolveTextBodyContentElement = (textElement: HTMLElement): HTMLElement => {
    for (const child of Array.from(textElement.children)) {
        if (child instanceof HTMLElement && child.getAttribute(TEXT_BODY_CONTENT_ATTRIBUTE) === 'true') {
            return child;
        }
    }
    const child = textElement.ownerDocument.createElement('span');
    child.className = TEXT_BODY_CONTENT_CLASS_NAME;
    child.setAttribute(TEXT_BODY_CONTENT_ATTRIBUTE, 'true');
    textElement.appendChild(child);
    return child;
};

const resolveTooltipText = (state: SpinnerStatusState, text: string): string => {
    return state.actionsElement && hasActiveMessageActionButton(state.actionsElement) ? normalizeSpinnerStatusText(text) : '';
};

const renderVisibleSpinnerStatusText = (normalizedText: string): string => {
    if (!normalizedText) {
        return '';
    }
    return normalizedText.endsWith(STATUS_TEXT_CONTINUATION_SUFFIX) ? normalizedText : `${normalizedText}${STATUS_TEXT_CONTINUATION_SUFFIX}`;
};

const clearStatusTextTransitionElement = (textElement: HTMLElement): void => {
    textElement.removeAttribute(TEXT_BODY_PREVIOUS_VALUE_ATTRIBUTE);
};

const finishStatusTextTransitionElement = (textElement: HTMLElement): void => {
    textElement.classList.remove(FADING_CLASS);
    clearStatusTextTransitionElement(textElement);
};

const prepareStatusTextTransition = (textElement: HTMLElement, nextVisibleText: string): void => {
    const currentVisibleText = textElement.getAttribute('data-stream-spinner-text-value') ?? resolveTextBodyContentElement(textElement).textContent ?? '';
    if (currentVisibleText && currentVisibleText !== nextVisibleText) {
        textElement.setAttribute(TEXT_BODY_PREVIOUS_VALUE_ATTRIBUTE, currentVisibleText);
        return;
    }
    clearStatusTextTransitionElement(textElement);
};

const syncStatusTooltipAttributes = (state: SpinnerStatusState): void => {
    const tooltipText = resolveTooltipText(state, state.lastShownText);
    if (state.labelElement) {
        applyTooltipAttributes(state.labelElement, tooltipText);
    }
    if (state.statusElement) {
        applyTooltipAttributes(state.statusElement, tooltipText);
    }
    if (state.actionsElement) {
        applyTooltipAttributes(state.actionsElement, tooltipText);
    }
};

const applyStatusText = (state: SpinnerStatusState, text: string): void => {
    const normalizedText = normalizeSpinnerStatusText(text);
    const visibleText = renderVisibleSpinnerStatusText(normalizedText);
    if (state.textElement) {
        resolveTextBodyContentElement(state.textElement).textContent = visibleText;
        state.textElement.setAttribute('data-stream-spinner-text-value', visibleText);
    }
    state.lastShownText = normalizedText;
    syncStatusTooltipAttributes(state);
};

const finalizeState = (documentRef: Document, state: SpinnerStatusState): void => {
    clearStateTimers(state);
    if (state.textElement) {
        finishStatusTextTransitionElement(state.textElement);
        state.textElement.classList.remove(VISIBILITY_FADING_CLASS);
    }
    if (getRuntimeStateByMessageId(documentRef, state.messageId) === state) {
        removeRuntimeStateByMessageId(documentRef, state.messageId);
    }
};

const startFade = (state: SpinnerStatusState, nextText: string, scheduleCheckpoint: (currentState: SpinnerStatusState) => void, canApplyText?: (currentState: SpinnerStatusState) => boolean): void => {
    const statusElement = state.statusElement;
    const textElement = state.textElement;
    if (!statusElement || !textElement || !statusElement.isConnected || !textElement.isConnected) {
        if (!canApplyText || canApplyText(state)) {
            applyStatusText(state, nextText);
        }
        return;
    }
    state.view = statusElement.ownerDocument.defaultView;
    state.pendingText = normalizeSpinnerStatusText(nextText);
    if (state.fadeTimer === null) {
        prepareStatusTextTransition(textElement, renderVisibleSpinnerStatusText(state.pendingText));
    }
    startFadingTextSwap(
        state,
        state.pendingText,
        FADING_CLASS,
        FADE_DURATION_MS,
        () => {
            const currentState = getRuntimeStateByMessageId(statusElement.ownerDocument, state.messageId) ?? null;
            return currentState === state ? currentState : null;
        },
        (currentState, text) => {
            if (!canApplyText || canApplyText(currentState)) {
                applyStatusText(currentState, text);
            }
        },
        finishStatusTextTransitionElement,
        scheduleCheckpoint
    );
};

export { applyStatusText, applyTooltipAttributes, clearSpinnerStatusRuntimeText, finalizeState, finishStatusTextTransitionElement, normalizeSpinnerStatusText, startFade, syncStatusTooltipAttributes };
