/* SoAI - Chat feature stream message spinner status state [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDocumentScopedStringKeyMap } from '@core/dom/documentScopedStringKeyMap.ts';
import { clearFadingTextTimers } from '@features/chat/stream/fadingTextScheduler.ts';
import type { StreamStatusMessageKey } from '@features/chat/stream/streamMessageSpinnerStatusText.ts';

const STREAM_SPINNER_VISIBILITY_DELAY_MS = 15_000;

interface SpinnerStatusState {
    messageId: string;
    messageRoot: HTMLElement | null;
    statusElement: HTMLElement | null;
    labelElement: HTMLElement | null;
    textElement: HTMLElement | null;
    actionsElement: HTMLElement | null;
    spinnerElement: HTMLElement | null;
    view: Window | null;
    visibilityRevealAtServerMs: number;
    visibilityRevealDelayElapsed: boolean;
    visibilityRevealTimer: number | null;
    scheduledVisibilityRevealAtServerMs: number | null;
    visibilityFadeTimer: number | null;
    firstRevealCleanupTimer: number | null;
    placeholderRotationTimer: number | null;
    visibilitySuppressed: boolean;
    checkpointTimer: number | null;
    fadeTimer: number | null;
    nextCheckpointAt: number;
    pendingText: string | null;
    realPreviewCooldownMs: number;
    lastRealPreviewTransitionStartedAtMs: number;
    placeholderKey: StreamStatusMessageKey;
    lastShownText: string;
    lastReconcileSignature: string;
    hasShownRealPreview: boolean;
    hasRevealedOnce: boolean;
}

type SpinnerStatusStateMap = Map<string, SpinnerStatusState>;

const stateByDocument = createDocumentScopedStringKeyMap<SpinnerStatusState>();

const clearSpinnerStatusTextTimers = (state: SpinnerStatusState): void => {
    clearFadingTextTimers(state);
};

const clearStateTimers = (state: SpinnerStatusState): void => {
    clearSpinnerStatusTextTimers(state);
    if (state.visibilityRevealTimer !== null && state.view !== null) {
        state.view.clearTimeout(state.visibilityRevealTimer);
        state.visibilityRevealTimer = null;
    }
    state.scheduledVisibilityRevealAtServerMs = null;
    if (state.visibilityFadeTimer !== null && state.view !== null) {
        state.view.clearTimeout(state.visibilityFadeTimer);
        state.visibilityFadeTimer = null;
    }
    if (state.firstRevealCleanupTimer !== null && state.view !== null) {
        state.view.clearTimeout(state.firstRevealCleanupTimer);
        state.firstRevealCleanupTimer = null;
    }
    if (state.placeholderRotationTimer !== null && state.view !== null) {
        state.view.clearTimeout(state.placeholderRotationTimer);
    }
    state.placeholderRotationTimer = null;
};

const createSpinnerStatusState = (inputArguments: { messageId: string; messageRoot: HTMLElement; statusElement: HTMLElement; labelElement: HTMLElement; textElement: HTMLElement; actionsElement: HTMLElement; spinnerElement: HTMLElement | null; view: Window; visibilityRevealAtServerMs: number; placeholderKey: StreamStatusMessageKey; lastShownText: string; hasShownRealPreview: boolean }): SpinnerStatusState => {
    return {
        messageId: inputArguments.messageId,
        messageRoot: inputArguments.messageRoot,
        statusElement: inputArguments.statusElement,
        labelElement: inputArguments.labelElement,
        textElement: inputArguments.textElement,
        actionsElement: inputArguments.actionsElement,
        spinnerElement: inputArguments.spinnerElement,
        view: inputArguments.view,
        visibilityRevealAtServerMs: inputArguments.visibilityRevealAtServerMs,
        visibilityRevealDelayElapsed: false,
        visibilityRevealTimer: null,
        scheduledVisibilityRevealAtServerMs: null,
        visibilityFadeTimer: null,
        firstRevealCleanupTimer: null,
        placeholderRotationTimer: null,
        visibilitySuppressed: false,
        checkpointTimer: null,
        fadeTimer: null,
        nextCheckpointAt: 0,
        pendingText: null,
        realPreviewCooldownMs: 0,
        lastRealPreviewTransitionStartedAtMs: -1,
        placeholderKey: inputArguments.placeholderKey,
        lastShownText: inputArguments.lastShownText,
        lastReconcileSignature: '',
        hasShownRealPreview: inputArguments.hasShownRealPreview,
        hasRevealedOnce: false
    };
};

const getRuntimeStateByMessageId = (documentRef: Document, messageId: string): SpinnerStatusState | undefined => {
    const state = stateByDocument.get(documentRef, messageId);
    return state ? state : undefined;
};

const setRuntimeStateByMessageId = (documentRef: Document, messageId: string, state: SpinnerStatusState): void => {
    stateByDocument.set(documentRef, messageId, state);
};

const removeRuntimeStateByMessageId = (documentRef: Document, messageId: string): void => {
    stateByDocument.delete(documentRef, messageId);
};

const getRuntimeStateByMessageIdMap = (documentRef: Document): SpinnerStatusStateMap => stateByDocument.requireMap(documentRef);

const clearRuntimeStateByDocument = (documentRef: Document): void => {
    stateByDocument.clear(documentRef);
};

export { clearRuntimeStateByDocument, clearSpinnerStatusTextTimers, clearStateTimers, createSpinnerStatusState, getRuntimeStateByMessageId, getRuntimeStateByMessageIdMap, removeRuntimeStateByMessageId, setRuntimeStateByMessageId };
export type { SpinnerStatusState, SpinnerStatusStateMap };
export { STREAM_SPINNER_VISIBILITY_DELAY_MS };
