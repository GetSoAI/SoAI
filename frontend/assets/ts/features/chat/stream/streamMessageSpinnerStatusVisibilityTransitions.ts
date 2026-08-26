/* SoAI - Applies show/hide transitions for streaming spinner/status without re-rendering [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusVisibilityTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveMaxCssTransitionTotalMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { getRuntimeStateByMessageId, type SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { FIRST_REVEAL_ATTRIBUTE, scheduleFirstRevealCleanup } from '@features/chat/stream/streamMessageSpinnerStatusFirstReveal.ts';
import { hasSettledActionButtons } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';
import { FADE_DURATION_MS, FADING_CLASS, VISIBILITY_FADING_CLASS } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';
import { STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE, STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE, STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { markVisibleRealPreviewDisplayed } from '@features/chat/stream/streamMessageSpinnerStatusPreviewCooldown.ts';

const hasSettledAssistantActionButtons = (actionsElement: HTMLElement): boolean => {
    return hasSettledActionButtons(actionsElement);
};

const setVisibilityAttribute = (actionsElement: HTMLElement, visible: boolean): void => {
    const shouldBeVisible = visible && !hasSettledAssistantActionButtons(actionsElement);
    actionsElement.setAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE, shouldBeVisible ? 'true' : 'false');
};

const cancelVisibilityFadeTimer = (state: SpinnerStatusState): void => {
    if (state.visibilityFadeTimer === null) {
        return;
    }
    if (!state.view) {
        state.visibilityFadeTimer = null;
        return;
    }
    state.view.clearTimeout(state.visibilityFadeTimer);
    state.visibilityFadeTimer = null;
};

const markCurrentVisiblePreviewDisplayed = (state: SpinnerStatusState, actionsElement: HTMLElement): void => {
    const hasPreview = actionsElement.getAttribute(STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE) === 'true';
    const previewText = actionsElement.getAttribute(STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE);
    markVisibleRealPreviewDisplayed(state, actionsElement, previewText, hasPreview);
};

const applyVisibilityWithFade = (documentRef: Document, state: SpinnerStatusState, actionsElement: HTMLElement, visible: boolean): void => {
    if (!state.view) {
        setVisibilityAttribute(actionsElement, visible);
        if (state.textElement) {
            state.textElement.classList.remove(VISIBILITY_FADING_CLASS);
        }
        return;
    }
    const shouldBeVisible = visible && !hasSettledAssistantActionButtons(actionsElement);
    const currentVisible = actionsElement.getAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE) === 'true';
    if (shouldBeVisible) {
        cancelVisibilityFadeTimer(state);
        if (currentVisible) {
            if (state.fadeTimer === null && state.textElement) {
                state.textElement.classList.remove(VISIBILITY_FADING_CLASS);
            }
            return;
        }
        const isFirstReveal = !state.hasRevealedOnce;
        state.hasRevealedOnce = true;
        if (isFirstReveal) {
            actionsElement.setAttribute(FIRST_REVEAL_ATTRIBUTE, 'true');
        }
        actionsElement.setAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE, 'true');
        markCurrentVisiblePreviewDisplayed(state, actionsElement);
        if (state.fadeTimer !== null) {
            return;
        }
        const textElement = state.textElement;
        if (!textElement || !textElement.isConnected) {
            return;
        }
        const spinnerElement = state.spinnerElement;
        textElement.classList.add(VISIBILITY_FADING_CLASS);
        if (spinnerElement && spinnerElement.isConnected) {
            spinnerElement.classList.add(FADING_CLASS);
        }
        state.view.requestAnimationFrame(() => {
            const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
            if (refreshed !== state || !refreshed.view) {
                return;
            }
            refreshed.view.requestAnimationFrame(() => {
                const stable = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
                if (stable !== state) {
                    return;
                }
                const stableTextElement = stable.textElement;
                if (stableTextElement && stableTextElement.isConnected) {
                    stableTextElement.classList.remove(VISIBILITY_FADING_CLASS);
                }
                const stableActionsElement = stable.actionsElement;
                const stableSpinnerElement = stable.spinnerElement;
                if (stableActionsElement && stableActionsElement.isConnected) {
                    if (stableSpinnerElement && stableSpinnerElement.isConnected) {
                        stableSpinnerElement.classList.remove(FADING_CLASS);
                    }
                    if (stableTextElement && stableTextElement.isConnected && stableActionsElement.getAttribute(FIRST_REVEAL_ATTRIBUTE) === 'true') {
                        scheduleFirstRevealCleanup(documentRef, stable, stableActionsElement, stableTextElement);
                    }
                }
            });
        });
        return;
    }
    if (!currentVisible) {
        if (state.fadeTimer === null && state.textElement) {
            state.textElement.classList.remove(VISIBILITY_FADING_CLASS);
        }
        actionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
        return;
    }
    if (state.visibilityFadeTimer !== null) {
        return;
    }
    actionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
    const textElement = state.textElement;
    if (textElement && textElement.isConnected) {
        textElement.classList.add(VISIBILITY_FADING_CLASS);
    }
    const spinnerElement = state.spinnerElement;
    if (spinnerElement && spinnerElement.isConnected) {
        spinnerElement.classList.add(FADING_CLASS);
    }
    const timeoutMs = textElement ? resolveMaxCssTransitionTotalMs(textElement) : 0;
    state.visibilityFadeTimer = state.view.setTimeout(
        (): void => {
            const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
            if (refreshed !== state) {
                return;
            }
            refreshed.visibilityFadeTimer = null;
            const refreshedActionsElement = refreshed.actionsElement;
            if (refreshedActionsElement && refreshedActionsElement.isConnected) {
                refreshedActionsElement.setAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE, 'false');
                refreshedActionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
            }
            const refreshedTextElement = refreshed.textElement;
            if (refreshedTextElement && refreshedTextElement.isConnected) {
                refreshedTextElement.classList.remove(VISIBILITY_FADING_CLASS);
            }
            const refreshedSpinnerElement = refreshed.spinnerElement;
            if (refreshedActionsElement && refreshedActionsElement.isConnected) {
                if (refreshedSpinnerElement && refreshedSpinnerElement.isConnected) {
                    refreshedSpinnerElement.classList.remove(FADING_CLASS);
                }
            }
        },
        Math.max(0, timeoutMs > 0 ? timeoutMs : FADE_DURATION_MS)
    );
};

export { applyVisibilityWithFade, cancelVisibilityFadeTimer, setVisibilityAttribute };
