/* SoAI - Chat feature fading text scheduler [frontend/assets/ts/features/chat/stream/fadingTextScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { monotonicMs } from '@core/time/clock.ts';

interface FadingTextSchedulerState<TText extends string> {
    view: Window | null;
    checkpointTimer: number | null;
    fadeTimer: number | null;
    nextCheckpointAt: number;
    textElement: HTMLElement | null;
    pendingText: TText | null;
}

const clearTimer = (view: Window | null, timer: number | null): void => {
    if (timer !== null && view) {
        view.clearTimeout(timer);
    }
};

const clearFadingTextTimers = <TText extends string>(state: Pick<FadingTextSchedulerState<TText>, 'view' | 'checkpointTimer' | 'fadeTimer' | 'pendingText'>): void => {
    clearTimer(state.view, state.checkpointTimer);
    clearTimer(state.view, state.fadeTimer);
    state.checkpointTimer = null;
    state.fadeTimer = null;
    state.pendingText = null;
};

const scheduleCheckpointTimer = <TText extends string>(state: Pick<FadingTextSchedulerState<TText>, 'view' | 'checkpointTimer' | 'fadeTimer' | 'nextCheckpointAt'>, onCheckpoint: () => void): void => {
    if (state.checkpointTimer !== null || state.fadeTimer !== null) {
        return;
    }
    const view = state.view;
    if (!view) {
        return;
    }
    const delay = Math.max(0, state.nextCheckpointAt - monotonicMs());
    state.checkpointTimer = view.setTimeout(() => {
        state.checkpointTimer = null;
        onCheckpoint();
    }, delay);
};

const startFadingTextSwap = <TText extends string, TState extends FadingTextSchedulerState<TText>>(state: TState, nextText: TText, fadeClassName: string, fadeDurationMs: number, getCurrentState: () => TState | null, applyText: (currentState: TState, text: TText) => void, finishTransition: (textElement: HTMLElement) => void, scheduleCheckpoint: (currentState: TState) => void): void => {
    const textElement = state.textElement;
    if (state.fadeTimer !== null) {
        state.pendingText = nextText;
        applyText(state, nextText);
        return;
    }
    if (!textElement || !textElement.isConnected || prefersReducedMotion(textElement)) {
        state.pendingText = null;
        applyText(state, nextText);
        scheduleCheckpoint(state);
        return;
    }
    state.pendingText = nextText;
    textElement.classList.add(fadeClassName);
    applyText(state, nextText);
    const view = state.view;
    if (!view) {
        state.pendingText = null;
        finishTransition(textElement);
        scheduleCheckpoint(state);
        return;
    }
    state.fadeTimer = view.setTimeout(() => {
        state.fadeTimer = null;
        const currentState = getCurrentState();
        if (!currentState) {
            finishTransition(textElement);
            return;
        }
        const pendingText = currentState.pendingText;
        currentState.pendingText = null;
        if (pendingText) {
            applyText(currentState, pendingText);
        }
        const currentTextElement = currentState.textElement && currentState.textElement.isConnected ? currentState.textElement : textElement;
        if (currentTextElement.isConnected) {
            finishTransition(currentTextElement);
        }
        scheduleCheckpoint(currentState);
    }, fadeDurationMs);
};

export { clearFadingTextTimers, scheduleCheckpointTimer, startFadingTextSwap };
export type { FadingTextSchedulerState };
