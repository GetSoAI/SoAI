/* SoAI - Manages the first-reveal attribute lifecycle for streaming spinner/status fade timing [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusFirstReveal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveSpinnerStatusTransitionDurationMs } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';
import { getRuntimeStateByMessageId, type SpinnerStatusState } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';

const FIRST_REVEAL_ATTRIBUTE = 'data-stream-spinner-first-reveal';

const scheduleFirstRevealCleanup = (documentRef: Document, state: SpinnerStatusState, actionsElement: HTMLElement, textElement: HTMLElement): void => {
    if (state.firstRevealCleanupTimer !== null) {
        return;
    }
    const view = state.view;
    if (!view) {
        actionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
        return;
    }
    const durationMs = resolveSpinnerStatusTransitionDurationMs(textElement, state.spinnerElement);
    if (durationMs <= 0) {
        actionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
        return;
    }
    const sequence = state.visibilityTransitionSequence;
    state.firstRevealCleanupTimer = view.setTimeout(() => {
        const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId);
        if (refreshed !== state || refreshed.visibilityTransitionSequence !== sequence || refreshed.actionsElement !== actionsElement) {
            return;
        }
        refreshed.firstRevealCleanupTimer = null;
        actionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
    }, durationMs);
};

export { FIRST_REVEAL_ATTRIBUTE, scheduleFirstRevealCleanup };
