/* SoAI - Manages the first-reveal attribute lifecycle for streaming spinner/status fade timing [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusFirstReveal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveMaxCssTransitionTotalMs } from '@core/animations/parseMaxCssDurationMs.ts';
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
    const durationMs = resolveMaxCssTransitionTotalMs(textElement);
    if (durationMs <= 0) {
        actionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
        return;
    }
    let finished = false;
    const finish = (): void => {
        textElement.removeEventListener('transitionend', onEnd);
        const refreshed = getRuntimeStateByMessageId(documentRef, state.messageId) ?? null;
        if (refreshed !== state) {
            return;
        }
        refreshed.firstRevealCleanupTimer = null;
        if (actionsElement.isConnected) {
            actionsElement.removeAttribute(FIRST_REVEAL_ATTRIBUTE);
        }
    };
    const onEnd = (event: TransitionEvent): void => {
        if (event.target !== textElement || event.propertyName !== 'opacity') {
            return;
        }
        if (finished) {
            return;
        }
        finished = true;
        finish();
    };
    textElement.addEventListener('transitionend', onEnd);
    state.firstRevealCleanupTimer = view.setTimeout(
        () => {
            if (finished) {
                return;
            }
            finished = true;
            finish();
        },
        Math.max(0, durationMs)
    );
};

export { FIRST_REVEAL_ATTRIBUTE, scheduleFirstRevealCleanup };
