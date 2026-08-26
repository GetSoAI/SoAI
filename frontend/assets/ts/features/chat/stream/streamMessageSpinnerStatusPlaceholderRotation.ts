/* SoAI - Streaming spinner placeholder status rotation [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusPlaceholderRotation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getRuntimeStateByMessageId, type SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { applyImmediateSpinnerStatusText } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeState.ts';
import { normalizeSpinnerStatusText, startFade } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';
import { chooseNextKey, getStatusMessageText } from '@features/chat/stream/streamMessageSpinnerStatusText.ts';
import { STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE, STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE } from '@features/chat/stream/streamMessageSpinnerStatusAttributes.ts';
import { hasRunningContextCompactionActivity, hasRunningWaitActivity } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';

const PLACEHOLDER_ROTATION_INTERVAL_MS = 8_000;

const clearPlaceholderRotationTimer = (state: SpinnerStatusState): void => {
    if (state.placeholderRotationTimer !== null && state.view !== null) {
        state.view.clearTimeout(state.placeholderRotationTimer);
    }
    state.placeholderRotationTimer = null;
};

const canRotatePlaceholder = (state: SpinnerStatusState): boolean => {
    const statusElement = state.statusElement;
    const actionsElement = state.actionsElement;
    const messageRoot = state.messageRoot;
    if (!statusElement || !statusElement.isConnected || !actionsElement || !actionsElement.isConnected || !messageRoot || !messageRoot.isConnected) {
        return false;
    }
    if (actionsElement.getAttribute('data-message-streaming') !== 'true') {
        return false;
    }
    if (actionsElement.getAttribute('data-user-input-required') === 'true') {
        return false;
    }
    if (hasRunningContextCompactionActivity(messageRoot) || hasRunningWaitActivity(messageRoot)) {
        return false;
    }
    const hasPreview = actionsElement.getAttribute(STREAM_SPINNER_HAS_PREVIEW_ATTRIBUTE) === 'true';
    const previewText = (actionsElement.getAttribute(STREAM_SPINNER_PREVIEW_TEXT_ATTRIBUTE) ?? '').trim();
    return !hasPreview || previewText.length === 0;
};

const schedulePlaceholderRotation = (documentRef: Document, state: SpinnerStatusState): void => {
    if (state.placeholderRotationTimer !== null || state.view === null) {
        return;
    }
    state.placeholderRotationTimer = state.view.setTimeout((): void => {
        const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
        if (refreshed !== state) {
            return;
        }
        refreshed.placeholderRotationTimer = null;
        if (!canRotatePlaceholder(refreshed)) {
            return;
        }
        const nextKey = chooseNextKey(refreshed.placeholderKey);
        refreshed.placeholderKey = nextKey;
        startFade(
            refreshed,
            getStatusMessageText(nextKey),
            () => {
                if (canRotatePlaceholder(refreshed)) {
                    schedulePlaceholderRotation(documentRef, refreshed);
                }
            },
            canRotatePlaceholder
        );
    }, PLACEHOLDER_ROTATION_INTERVAL_MS);
};

const reconcilePlaceholderRotation = (documentRef: Document, state: SpinnerStatusState): void => {
    if (!canRotatePlaceholder(state)) {
        clearPlaceholderRotationTimer(state);
        return;
    }
    const placeholderText = getStatusMessageText(state.placeholderKey);
    if (state.lastShownText !== normalizeSpinnerStatusText(placeholderText)) {
        applyImmediateSpinnerStatusText(state, placeholderText);
    }
    schedulePlaceholderRotation(documentRef, state);
};

export { clearPlaceholderRotationTimer, reconcilePlaceholderRotation };
