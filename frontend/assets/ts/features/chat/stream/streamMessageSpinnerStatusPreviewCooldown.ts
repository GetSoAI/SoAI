/* SoAI - Streaming spinner status preview cooldown reconciliation [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusPreviewCooldown.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireNonNegativeIntegerAttribute } from '@core/dom/attributes.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { scheduleCheckpointTimer } from '@features/chat/stream/fadingTextScheduler.ts';
import { STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE, STREAM_SPINNER_VISIBLE_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { clearSpinnerStatusTextTimers, type SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { normalizeSpinnerStatusText, startFade } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';
import { applyImmediateSpinnerStatusText } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeState.ts';

const STATUS_PREVIEW_COOLDOWN_CONTEXT = 'Streaming spinner status preview';

const readPreviewCooldownMs = (actionsElement: HTMLElement, hasPreview: boolean): number => {
    if (!hasPreview) {
        return 0;
    }
    const cooldownMs = requireNonNegativeIntegerAttribute(actionsElement, STREAM_SPINNER_PREVIEW_COOLDOWN_MS_ATTRIBUTE, STATUS_PREVIEW_COOLDOWN_CONTEXT);
    if (cooldownMs <= 0) {
        throw new Error('Streaming spinner status preview cooldown must be positive.');
    }
    return cooldownMs;
};

const isStatusCurrentlyVisible = (actionsElement: HTMLElement): boolean => {
    return actionsElement.getAttribute(STREAM_SPINNER_VISIBLE_ATTRIBUTE) === 'true';
};

const clearPreviewCooldownCheckpoint = (state: SpinnerStatusState): void => {
    if (state.checkpointTimer !== null && state.view !== null) {
        state.view.clearTimeout(state.checkpointTimer);
    }
    state.checkpointTimer = null;
};

const schedulePreviewCooldownCheckpoint = (state: SpinnerStatusState, onCheckpoint: () => void): void => {
    scheduleCheckpointTimer(state, onCheckpoint);
};

const markVisibleRealPreviewDisplayed = (state: SpinnerStatusState, actionsElement: HTMLElement, previewText: string | null, hasPreview: boolean): void => {
    if (!hasPreview || !previewText || !isStatusCurrentlyVisible(actionsElement)) {
        return;
    }
    if (state.lastShownText !== normalizeSpinnerStatusText(previewText)) {
        return;
    }
    if (state.lastRealPreviewTransitionStartedAtMs < 0) {
        state.lastRealPreviewTransitionStartedAtMs = monotonicMs();
    }
};

const reconcileRealPreviewText = (inputArguments: { state: SpinnerStatusState; actionsElement: HTMLElement; previewText: string; cooldownMs: number; onCheckpoint: () => void }): void => {
    const { state, actionsElement, previewText, cooldownMs, onCheckpoint } = inputArguments;
    const normalizedPreviewText = normalizeSpinnerStatusText(previewText);
    state.realPreviewCooldownMs = cooldownMs;
    state.hasShownRealPreview = true;
    if (state.lastShownText === normalizedPreviewText) {
        clearPreviewCooldownCheckpoint(state);
        markVisibleRealPreviewDisplayed(state, actionsElement, previewText, true);
        return;
    }
    if (!isStatusCurrentlyVisible(actionsElement)) {
        clearSpinnerStatusTextTimers(state);
        applyImmediateSpinnerStatusText(state, previewText);
        state.lastRealPreviewTransitionStartedAtMs = -1;
        return;
    }
    const nowMs = monotonicMs();
    const lastTransitionMs = state.lastRealPreviewTransitionStartedAtMs;
    if (lastTransitionMs >= 0) {
        const nextAllowedAtMs = lastTransitionMs + cooldownMs;
        if (nowMs < nextAllowedAtMs) {
            state.nextCheckpointAt = nextAllowedAtMs;
            schedulePreviewCooldownCheckpoint(state, onCheckpoint);
            return;
        }
    }
    clearPreviewCooldownCheckpoint(state);
    state.lastRealPreviewTransitionStartedAtMs = nowMs;
    state.nextCheckpointAt = nowMs + cooldownMs;
    startFade(state, previewText, (currentState) => {
        schedulePreviewCooldownCheckpoint(currentState, onCheckpoint);
    });
};

const reconcileSpinnerStatusPreviewText = (inputArguments: { state: SpinnerStatusState; actionsElement: HTMLElement; previewText: string | null; hasPreview: boolean; onCheckpoint: () => void }): boolean => {
    const cooldownMs = readPreviewCooldownMs(inputArguments.actionsElement, inputArguments.hasPreview);
    if (!inputArguments.hasPreview || !inputArguments.previewText) {
        inputArguments.state.realPreviewCooldownMs = 0;
        clearPreviewCooldownCheckpoint(inputArguments.state);
        return false;
    }
    reconcileRealPreviewText({
        state: inputArguments.state,
        actionsElement: inputArguments.actionsElement,
        previewText: inputArguments.previewText,
        cooldownMs,
        onCheckpoint: inputArguments.onCheckpoint
    });
    return true;
};

export { markVisibleRealPreviewDisplayed, reconcileSpinnerStatusPreviewText };
