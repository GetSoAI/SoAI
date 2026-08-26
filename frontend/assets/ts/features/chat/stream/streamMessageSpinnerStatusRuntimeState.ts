/* SoAI - Streaming spinner status runtime state creation and binding [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusRuntimeState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireNonNegativeIntegerAttribute } from '@core/dom/attributes.ts';
import { applyStatusText, FADING_CLASS, finishStatusTextTransitionElement } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';
import { STREAM_SPINNER_VISIBILITY_DELAY_MS, createSpinnerStatusState, setRuntimeStateByMessageId, type SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { chooseNextKey, getStatusMessageText } from '@features/chat/stream/streamMessageSpinnerStatusText.ts';
import { STREAM_SPINNER_TRIGGER_USER_AT_MS_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';

type CreateSpinnerStatusRuntimeStateArguments = {
    documentRef: Document;
    messageId: string;
    messageRoot: HTMLElement;
    statusElement: HTMLElement;
    labelElement: HTMLElement;
    bodyElement: HTMLElement;
    actionsElement: HTMLElement;
    spinnerElement: HTMLElement | null;
    previewText: string | null;
    hasPreview: boolean;
};

const bindSpinnerStatusState = (state: SpinnerStatusState, messageRoot: HTMLElement, statusElement: HTMLElement, labelElement: HTMLElement, textElement: HTMLElement, actionsElement: HTMLElement, spinnerElement: HTMLElement | null): void => {
    state.messageRoot = messageRoot;
    state.statusElement = statusElement;
    state.labelElement = labelElement;
    state.textElement = textElement;
    state.actionsElement = actionsElement;
    state.spinnerElement = spinnerElement;
    state.view = statusElement.ownerDocument.defaultView;
    textElement.classList.toggle(FADING_CLASS, state.pendingText !== null && state.fadeTimer !== null);
    if (state.pendingText === null || state.fadeTimer === null) {
        finishStatusTextTransitionElement(textElement);
    }
};

const applyImmediateSpinnerStatusText = (state: SpinnerStatusState, text: string): void => {
    state.pendingText = null;
    if (state.textElement) {
        finishStatusTextTransitionElement(state.textElement);
    }
    applyStatusText(state, text);
};

const createSpinnerStatusRuntimeState = (inputArguments: CreateSpinnerStatusRuntimeStateArguments): SpinnerStatusState => {
    const view = inputArguments.statusElement.ownerDocument.defaultView;
    if (!view) {
        throw new Error('Streaming spinner status is missing window context.');
    }
    const placeholderKey = chooseNextKey(null);
    const initialText = inputArguments.hasPreview && inputArguments.previewText ? inputArguments.previewText : getStatusMessageText(placeholderKey);
    const triggerUserTimestamp = requireNonNegativeIntegerAttribute(inputArguments.actionsElement, STREAM_SPINNER_TRIGGER_USER_AT_MS_ATTRIBUTE, 'Streaming spinner reveal delay');
    const state = createSpinnerStatusState({
        messageId: inputArguments.messageId,
        messageRoot: inputArguments.messageRoot,
        statusElement: inputArguments.statusElement,
        labelElement: inputArguments.labelElement,
        textElement: inputArguments.bodyElement,
        actionsElement: inputArguments.actionsElement,
        spinnerElement: inputArguments.spinnerElement,
        view,
        visibilityRevealAtServerMs: triggerUserTimestamp === 0 ? 0 : triggerUserTimestamp + STREAM_SPINNER_VISIBILITY_DELAY_MS,
        placeholderKey,
        lastShownText: initialText,
        hasShownRealPreview: inputArguments.hasPreview && inputArguments.previewText !== null
    });
    bindSpinnerStatusState(state, inputArguments.messageRoot, inputArguments.statusElement, inputArguments.labelElement, inputArguments.bodyElement, inputArguments.actionsElement, inputArguments.spinnerElement);
    applyImmediateSpinnerStatusText(state, initialText);
    setRuntimeStateByMessageId(inputArguments.documentRef, inputArguments.messageId, state);
    return state;
};

export { applyImmediateSpinnerStatusText, bindSpinnerStatusState, createSpinnerStatusRuntimeState };
