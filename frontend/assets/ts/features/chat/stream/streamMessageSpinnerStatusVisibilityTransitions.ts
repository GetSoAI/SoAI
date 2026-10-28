/* SoAI - Applies show/hide transitions for streaming spinner/status without re-rendering [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusVisibilityTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getRuntimeStateByMessageId, type SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { FIRST_REVEAL_ATTRIBUTE, scheduleFirstRevealCleanup } from '@features/chat/stream/streamMessageSpinnerStatusFirstReveal.ts';
import { hasSettledActionButtons, resolveSpinnerStatusTransitionDurationMs } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';
import { FADE_DURATION_MS, FADING_CLASS, VISIBILITY_FADING_CLASS } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';
import { STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE, STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE, STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { markVisibleRealPreviewDisplayed } from '@features/chat/stream/streamMessageSpinnerStatusPreviewCooldown.ts';

const setVisibilityAttribute = (actionsElement: HTMLElement, visible: boolean): void => {
    const shouldBeVisible = visible && !hasSettledActionButtons(actionsElement);
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
    const shouldBeVisible = visible && !hasSettledActionButtons(actionsElement);
    const currentVisible = actionsElement.getAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE) === 'true';
    if (shouldBeVisible) {
        const wasHiding = state.visibilityFadeTimer !== null;
        cancelVisibilityFadeTimer(state);
        if (wasHiding) {
            state.visibilityTransitionSequence += 1;
            state.spinnerElement?.classList.remove(FADING_CLASS);
            state.textElement?.classList.remove(VISIBILITY_FADING_CLASS);
        }
        if (currentVisible) {
            state.hasRevealedOnce = true;
            if (state.visibilityRevealFrame === null && state.fadeTimer === null && state.textElement) {
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
        const sequence = ++state.visibilityTransitionSequence;
        state.visibilityRevealFrame = state.view.requestAnimationFrame(() => {
            const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
            if (refreshed !== state || !refreshed.view || refreshed.visibilityTransitionSequence !== sequence || refreshed.actionsElement !== actionsElement) {
                return;
            }
            refreshed.visibilityRevealFrame = refreshed.view.requestAnimationFrame(() => {
                const stable = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
                if (stable !== state || stable.visibilityTransitionSequence !== sequence || stable.actionsElement !== actionsElement) {
                    return;
                }
                stable.visibilityRevealFrame = null;
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
    state.visibilityTransitionSequence += 1;
    if (state.firstRevealCleanupTimer !== null) {
        state.view.clearTimeout(state.firstRevealCleanupTimer);
        state.firstRevealCleanupTimer = null;
    }
    if (state.visibilityRevealFrame !== null) {
        state.view.cancelAnimationFrame(state.visibilityRevealFrame);
        state.visibilityRevealFrame = null;
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
    const timeoutMs = resolveSpinnerStatusTransitionDurationMs(textElement, spinnerElement);
    const sequence = state.visibilityTransitionSequence;
    state.visibilityFadeTimer = state.view.setTimeout(
        (): void => {
            const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
            if (refreshed !== state || refreshed.visibilityTransitionSequence !== sequence || refreshed.actionsElement !== actionsElement) {
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
