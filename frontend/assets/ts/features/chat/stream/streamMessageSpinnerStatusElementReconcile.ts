/* SoAI - Reconciles streaming spinner/status UI for a message without re-rendering [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusElementReconcile.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { clearSpinnerStatusTextTimers, getRuntimeStateByMessageId, type SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { finalizeState, finishStatusTextTransitionElement, normalizeSpinnerStatusText, syncStatusTooltipAttributes } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';
import { hasRunningContextCompactionActivity, hasRunningLoadingActivity, hasRunningWaitActivity, hasVisibleSpinnerActivity, requireStatusTextBodyElement, requireStatusTextElement, resolveActionsElement, resolveMessageId, resolveOwningMessageRoot, resolveSpinnerElement } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';
import { STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE, STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { applyVisibilityWithFade } from '@features/chat/stream/streamMessageSpinnerStatusVisibilityTransitions.ts';
import { applyImmediateSpinnerStatusText, bindSpinnerStatusState, createSpinnerStatusRuntimeState } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeState.ts';
import { markVisibleRealPreviewDisplayed, reconcileSpinnerStatusPreviewText } from '@features/chat/stream/streamMessageSpinnerStatusPreviewCooldown.ts';
import { resolveContextCompactionStreamPreviewText } from '@features/chat/stream/contextCompactionStreamPreview.ts';
import { clearPlaceholderRotationTimer, reconcilePlaceholderRotation } from '@features/chat/stream/streamMessageSpinnerStatusPlaceholderRotation.ts';
import { canSkipStableSpinnerReconcile, resolveSpinnerReconcileSignature } from '@features/chat/stream/streamMessageSpinnerStatusReconcileSignature.ts';
import { reconcileNonStreamingSpinnerStatusElement } from '@features/chat/stream/streamMessageSpinnerStatusTerminalReconcile.ts';

const cancelVisibilityRevealTimer = (state: SpinnerStatusState): void => {
    if (state.visibilityRevealTimer === null) {
        state.scheduledVisibilityRevealAtServerMs = null;
        return;
    }
    if (!state.view) {
        state.visibilityRevealTimer = null;
        state.scheduledVisibilityRevealAtServerMs = null;
        return;
    }
    state.view.clearTimeout(state.visibilityRevealTimer);
    state.visibilityRevealTimer = null;
    state.scheduledVisibilityRevealAtServerMs = null;
};

const scheduleVisibilityReveal = (documentRef: Document, state: SpinnerStatusState): void => {
    if (state.visibilitySuppressed) {
        return;
    }
    if (state.visibilityRevealTimer !== null && state.scheduledVisibilityRevealAtServerMs === state.visibilityRevealAtServerMs) {
        return;
    }
    if (state.view === null) {
        return;
    }
    if (state.visibilityRevealTimer !== null) {
        cancelVisibilityRevealTimer(state);
    }
    const remainingMs = Math.max(0, Math.ceil(state.visibilityRevealAtServerMs - serverEpochMs()));
    state.scheduledVisibilityRevealAtServerMs = state.visibilityRevealAtServerMs;
    state.visibilityRevealTimer = state.view.setTimeout((): void => {
        const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
        if (refreshed !== state || refreshed.view === null) {
            return;
        }
        refreshed.visibilityRevealTimer = null;
        refreshed.scheduledVisibilityRevealAtServerMs = null;
        refreshed.visibilityRevealDelayElapsed = true;
        refreshed.lastReconcileSignature = '';
        const refreshedStatusElement = refreshed.statusElement;
        if (!refreshedStatusElement || !refreshedStatusElement.isConnected) {
            return;
        }
        reconcileStreamingSpinnerStatusElement({ documentRef, statusElement: refreshedStatusElement });
    }, remainingMs);
};

const reconcileVisibility = (documentRef: Document, state: SpinnerStatusState, actionsElement: HTMLElement, messageRoot: HTMLElement, hasPreview: boolean): void => {
    if (state.visibilitySuppressed) {
        applyVisibilityWithFade(documentRef, state, actionsElement, false);
        return;
    }
    if (!hasVisibleSpinnerActivity(messageRoot)) {
        cancelVisibilityRevealTimer(state);
        applyVisibilityWithFade(documentRef, state, actionsElement, hasPreview);
        return;
    }
    if (!state.hasRevealedOnce && !state.visibilityRevealDelayElapsed && hasRunningLoadingActivity(messageRoot) && serverEpochMs() < state.visibilityRevealAtServerMs) {
        applyVisibilityWithFade(documentRef, state, actionsElement, false);
        scheduleVisibilityReveal(documentRef, state);
        return;
    }
    if (hasPreview) {
        cancelVisibilityRevealTimer(state);
        applyVisibilityWithFade(documentRef, state, actionsElement, true);
        return;
    }
    if (!hasRunningLoadingActivity(messageRoot)) {
        cancelVisibilityRevealTimer(state);
        applyVisibilityWithFade(documentRef, state, actionsElement, true);
        return;
    }
    applyVisibilityWithFade(documentRef, state, actionsElement, true);
};

const resolveSpinnerOverrideText = (messageRoot: HTMLElement, actionsElement: HTMLElement): string | null => {
    if (actionsElement.getAttribute('data-user-input-required') === 'true') {
        return i18n.t('chat.stream.preview.phases.waiting_for_user.1');
    }
    if (hasRunningContextCompactionActivity(messageRoot)) {
        return resolveContextCompactionStreamPreviewText();
    }
    const isWaitingToolActive = hasRunningWaitActivity(messageRoot);
    return isWaitingToolActive ? i18n.t('chat.stream.preview.tools.wait.1') : null;
};

const resolveStreamingPreviewState = (actionsElement: HTMLElement): { text: string | null; hasPreview: boolean } => {
    const hasPreview = actionsElement.getAttribute(STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE) === 'true';
    const previewText = (actionsElement.getAttribute(STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE) ?? '').trim();
    if (!hasPreview || !previewText) {
        return { text: null, hasPreview: false };
    }
    return { text: previewText, hasPreview: true };
};

const scheduleStatusPreviewCheckpoint = (documentRef: Document, state: SpinnerStatusState): (() => void) => {
    return (): void => {
        const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
        if (refreshed !== state) {
            return;
        }
        const statusElement = refreshed?.statusElement ?? null;
        if (!statusElement || !statusElement.isConnected) {
            finalizeState(documentRef, refreshed);
            return;
        }
        reconcileStreamingSpinnerStatusElement({ documentRef, statusElement });
    };
};

const reconcileStableText = (documentRef: Document, state: SpinnerStatusState, actionsElement: HTMLElement, previewText: string | null, hasPreview: boolean): void => {
    if (
        reconcileSpinnerStatusPreviewText({
            state,
            actionsElement,
            previewText,
            hasPreview,
            onCheckpoint: scheduleStatusPreviewCheckpoint(documentRef, state)
        })
    ) {
        clearPlaceholderRotationTimer(state);
        return;
    }
    reconcilePlaceholderRotation(documentRef, state);
};

const reconcileStreamingSpinnerStatusElement = (inputArguments: { documentRef: Document; statusElement: HTMLElement }): void => {
    const { documentRef, statusElement } = inputArguments;
    const messageRoot = resolveOwningMessageRoot(statusElement);
    const messageId = resolveMessageId(messageRoot);
    const labelElement = requireStatusTextElement(statusElement);
    const bodyElement = requireStatusTextBodyElement(labelElement);
    const actionsElement = resolveActionsElement(statusElement);
    const spinnerElement = resolveSpinnerElement(actionsElement);
    const overrideText = resolveSpinnerOverrideText(messageRoot, actionsElement);
    const isStreamingMessage = actionsElement.getAttribute('data-message-streaming') === 'true';
    const existing = getRuntimeStateByMessageId(documentRef, messageId) ?? null;

    if (!isStreamingMessage) {
        reconcileNonStreamingSpinnerStatusElement({ documentRef, state: existing, statusElement, labelElement, actionsElement, bodyElement });
        return;
    }

    const { text: previewText, hasPreview } = resolveStreamingPreviewState(actionsElement);
    const reboundElements = existing !== null && (existing.messageRoot !== messageRoot || existing.statusElement !== statusElement || existing.labelElement !== labelElement || existing.textElement !== bodyElement || existing.actionsElement !== actionsElement || existing.spinnerElement !== spinnerElement);
    const state = existing ?? createSpinnerStatusRuntimeState({ documentRef, messageId, messageRoot, statusElement, labelElement, bodyElement, actionsElement, spinnerElement, previewText, hasPreview });
    bindSpinnerStatusState(state, messageRoot, statusElement, labelElement, bodyElement, actionsElement, spinnerElement);
    const reconcileSignature = resolveSpinnerReconcileSignature({ messageId, actionsElement, messageRoot, hasPreview, previewText, overrideText });
    const expectedStableText = overrideText !== null ? normalizeSpinnerStatusText(overrideText) : hasPreview && previewText !== null ? normalizeSpinnerStatusText(previewText) : null;
    if (!reboundElements && canSkipStableSpinnerReconcile(state, reconcileSignature, hasPreview, expectedStableText)) {
        return;
    }
    state.lastReconcileSignature = reconcileSignature;
    syncStatusTooltipAttributes(state);

    if (overrideText) {
        clearPlaceholderRotationTimer(state);
        clearSpinnerStatusTextTimers(state);
        if (state.textElement) {
            finishStatusTextTransitionElement(state.textElement);
        }
        state.realPreviewCooldownMs = 0;
        state.lastRealPreviewTransitionStartedAtMs = -1;
        if (state.lastShownText !== normalizeSpinnerStatusText(overrideText)) {
            applyImmediateSpinnerStatusText(state, overrideText);
        }
        reconcileVisibility(documentRef, state, actionsElement, messageRoot, true);
        return;
    }

    reconcileStableText(documentRef, state, actionsElement, previewText, hasPreview);
    reconcileVisibility(documentRef, state, actionsElement, messageRoot, hasPreview);
    markVisibleRealPreviewDisplayed(state, actionsElement, previewText, hasPreview);
};

export { reconcileStreamingSpinnerStatusElement };
