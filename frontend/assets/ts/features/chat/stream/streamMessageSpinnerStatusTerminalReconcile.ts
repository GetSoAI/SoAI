/* SoAI - Streaming spinner status terminal teardown reconciliation [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusTerminalReconcile.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveMaxCssTransitionTotalMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { FIRST_REVEAL_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusFirstReveal.ts';
import { clearStateTimers, getRuntimeStateByMessageId, type SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { clearSpinnerStatusRuntimeText, FADE_DURATION_MS, FADING_CLASS, finalizeState, finishStatusTextTransitionElement, VISIBILITY_FADING_CLASS } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';
import { setVisibilityAttribute } from '@features/chat/stream/streamMessageSpinnerStatusVisibilityTransitions.ts';

const reconcileNonStreamingSpinnerStatusElement = (inputArguments: { documentRef: Document; state: SpinnerStatusState | null; statusElement: HTMLElement; labelElement: HTMLElement; actionsElement: HTMLElement; bodyElement: HTMLElement }): void => {
    const { documentRef, state, statusElement, labelElement, actionsElement, bodyElement } = inputArguments;
    actionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
    if (!state) {
        setVisibilityAttribute(actionsElement, false);
        finishStatusTextTransitionElement(bodyElement);
        bodyElement.classList.remove(VISIBILITY_FADING_CLASS);
        clearSpinnerStatusRuntimeText(statusElement, labelElement, bodyElement, actionsElement);
        return;
    }
    if (state.visibilityFadeTimer !== null) {
        clearStateTimers(state);
        setVisibilityAttribute(actionsElement, false);
        finishStatusTextTransitionElement(bodyElement);
        bodyElement.classList.remove(VISIBILITY_FADING_CLASS);
        clearSpinnerStatusRuntimeText(statusElement, labelElement, bodyElement, actionsElement);
        finalizeState(documentRef, state);
        return;
    }
    state.visibilitySuppressed = true;
    clearStateTimers(state);
    const view = state.view;
    const currentlyVisible = actionsElement.getAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE) === 'true';
    if (view && currentlyVisible) {
        const spinnerElement = state.spinnerElement;
        bodyElement.classList.add(VISIBILITY_FADING_CLASS);
        if (spinnerElement && spinnerElement.isConnected) {
            spinnerElement.classList.add(FADING_CLASS);
        }
        const timeoutMs = resolveMaxCssTransitionTotalMs(bodyElement);
        state.visibilityFadeTimer = view.setTimeout(
            (): void => {
                const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
                if (refreshed !== state) {
                    return;
                }
                refreshed.visibilityFadeTimer = null;
                if (!actionsElement.isConnected) {
                    return;
                }
                actionsElement.setAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE, 'false');
                bodyElement.classList.remove(VISIBILITY_FADING_CLASS);
                clearSpinnerStatusRuntimeText(statusElement, labelElement, bodyElement, actionsElement);
                if (spinnerElement && spinnerElement.isConnected) {
                    spinnerElement.classList.remove(FADING_CLASS);
                }
                finalizeState(documentRef, refreshed);
            },
            Math.max(0, timeoutMs > 0 ? timeoutMs : FADE_DURATION_MS)
        );
        return;
    }
    setVisibilityAttribute(actionsElement, false);
    finishStatusTextTransitionElement(bodyElement);
    bodyElement.classList.remove(VISIBILITY_FADING_CLASS);
    clearSpinnerStatusRuntimeText(statusElement, labelElement, bodyElement, actionsElement);
    finalizeState(documentRef, state);
};

export { reconcileNonStreamingSpinnerStatusElement };
