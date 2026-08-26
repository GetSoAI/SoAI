/* SoAI - Chat feature runtime [frontend/assets/ts/features/chat/stream/thinkingpreviewruntime/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stripTrailingPreviewDot, THINKING_PREVIEW_ATTRIBUTE_NAMES } from '@features/chat/message/messageview/inlineActivityText.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { scheduleCheckpointTimer } from '@features/chat/stream/fadingTextScheduler.ts';
import { clearThinkingPreviewTimers, getThinkingPreviewState, setThinkingPreviewState, type ThinkingPreviewState } from '@features/chat/stream/thinkingPreviewStateStore.ts';
import { applyRenderedThinkingPreviewText, applyThinkingPreviewText, bindThinkingPreviewState, finalizeThinkingPreviewState, resetStreamingBuffer } from '@features/chat/stream/thinkingpreviewruntime/stateTransitions.ts';
import { readThinkingPreviewAttribute, readThinkingPreviewStatus, requireThinkingPreviewCallId, requireThinkingPreviewTextElement, requireThinkingPreviewWindow } from '@features/chat/stream/thinkingpreviewruntime/dom.ts';

const THINKING_PREVIEW_CHECKPOINT_DELAY_MS = 3000;
const THINKING_PREVIEW_STREAM_TICK_DELAY_MS = 44;
const THINKING_PREVIEW_STREAM_MAX_TICKS = 24;
const THINKING_PREVIEW_SENTENCE_COOLDOWN_MS = 4000;

const resolveWords = (value: string): string[] => {
    const trimmed = value.trim();
    return trimmed ? trimmed.split(/\s+/g) : [];
};

const scheduleCooldown = (state: ThinkingPreviewState): void => {
    state.cooldownUntilMs = monotonicMs() + THINKING_PREVIEW_SENTENCE_COOLDOWN_MS;
};

const applyPendingPreviewAndScheduleCheckpoint = (state: ThinkingPreviewState, pendingText: string, reconcileCheckpoint: (documentRef: Document, callId: string) => void): void => {
    resetStreamingBuffer(state);
    applyThinkingPreviewText(state, pendingText);
    scheduleThinkingPreviewCheckpoint(state, reconcileCheckpoint);
};

const finalizeStreamWithCooldown = (state: ThinkingPreviewState, pendingText: string, reconcileCheckpoint: (documentRef: Document, callId: string) => void): void => {
    resetStreamingBuffer(state);
    applyThinkingPreviewText(state, pendingText);
    scheduleCooldown(state);
    state.nextCheckpointAt = state.cooldownUntilMs;
    scheduleThinkingPreviewCheckpoint(state, reconcileCheckpoint);
};

const updateActiveStreamTarget = (state: ThinkingPreviewState, nextPreview: string): boolean => {
    if (state.pendingText === null || state.streamWords === null || state.streamWordIndex <= 0) {
        return false;
    }
    const normalizedPreview = stripTrailingPreviewDot(nextPreview);
    if (!normalizedPreview || normalizedPreview === state.pendingText) {
        return false;
    }
    const nextWords = resolveWords(normalizedPreview);
    if (nextWords.length <= 0) {
        return false;
    }
    const currentIndex = Math.min(state.streamWordIndex, state.streamWords.length);
    if (currentIndex <= 0 || currentIndex > nextWords.length) {
        return false;
    }
    for (let index = 0; index < currentIndex; index += 1) {
        if (state.streamWords[index] !== nextWords[index]) {
            return false;
        }
    }
    state.pendingText = normalizedPreview;
    state.streamWords = nextWords;
    state.streamWordsPerTick = Math.max(1, Math.ceil(nextWords.length / THINKING_PREVIEW_STREAM_MAX_TICKS));
    return true;
};

const scheduleThinkingPreviewCheckpoint = (state: ThinkingPreviewState, reconcileCheckpoint: (documentRef: Document, callId: string) => void): void => {
    const queryElement = state.queryElement;
    if (!queryElement || !queryElement.isConnected) {
        finalizeThinkingPreviewState(state);
        return;
    }
    if (readThinkingPreviewStatus(queryElement) !== 'running') {
        return;
    }
    state.view = requireThinkingPreviewWindow(queryElement);
    if (state.cooldownUntilMs > 0) {
        state.nextCheckpointAt = Math.max(state.nextCheckpointAt, state.cooldownUntilMs);
    }
    scheduleCheckpointTimer(state, () => {
        reconcileCheckpoint(state.document, state.callId);
    });
};

const scheduleThinkingPreviewStreamTick = (state: ThinkingPreviewState, expectedSequence: number, reconcileTick: (documentRef: Document, callId: string) => void): void => {
    const queryElement = state.queryElement;
    const view = state.view;
    if (!queryElement || !queryElement.isConnected || !view) {
        return;
    }
    if (state.fadeTimer !== null) {
        return;
    }
    const documentRef = state.document;
    const callId = state.callId;
    state.fadeTimer = view.setTimeout((): void => {
        const currentState = getThinkingPreviewState(documentRef, callId);
        if (!currentState) {
            return;
        }
        currentState.fadeTimer = null;
        if (currentState.streamSequence !== expectedSequence) {
            return;
        }
        reconcileTick(documentRef, callId);
    }, THINKING_PREVIEW_STREAM_TICK_DELAY_MS);
};

const reconcileThinkingPreviewStreamTick = (documentRef: Document, callId: string, reconcileCheckpoint: (documentRef: Document, callId: string) => void, reconcileTick: (documentRef: Document, callId: string) => void): void => {
    const state = getThinkingPreviewState(documentRef, callId);
    if (!state) {
        return;
    }
    const queryElement = state.queryElement;
    const textElement = state.textElement;
    const pendingText = state.pendingText;
    const words = state.streamWords;
    if (!pendingText || !words || words.length <= 0) {
        scheduleThinkingPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    if (!queryElement || !textElement || !queryElement.isConnected || !textElement.isConnected) {
        finalizeThinkingPreviewState(state);
        return;
    }
    if (readThinkingPreviewStatus(queryElement) !== 'running') {
        resetStreamingBuffer(state);
        applyThinkingPreviewText(state, pendingText);
        finalizeThinkingPreviewState(state);
        return;
    }
    const nextIndex = Math.min(words.length, state.streamWordIndex + Math.max(1, state.streamWordsPerTick));
    state.streamWordIndex = nextIndex;
    applyRenderedThinkingPreviewText(state, words.slice(0, nextIndex).join(' '), { syncVisibleAttribute: false });
    if (nextIndex >= words.length) {
        finalizeStreamWithCooldown(state, pendingText, reconcileCheckpoint);
        return;
    }
    scheduleThinkingPreviewStreamTick(state, state.streamSequence, reconcileTick);
};

const startThinkingPreviewStream = (state: ThinkingPreviewState, nextPreview: string, reconcileCheckpoint: (documentRef: Document, callId: string) => void, reconcileTick: (documentRef: Document, callId: string) => void): void => {
    const queryElement = state.queryElement;
    const textElement = state.textElement;
    if (!queryElement || !textElement || !queryElement.isConnected || !textElement.isConnected) {
        applyPendingPreviewAndScheduleCheckpoint(state, nextPreview, reconcileCheckpoint);
        return;
    }
    clearThinkingPreviewTimers(state);
    state.view = requireThinkingPreviewWindow(queryElement);
    const normalizedPreview = stripTrailingPreviewDot(nextPreview);
    const words = resolveWords(normalizedPreview);
    if (words.length <= 0) {
        resetStreamingBuffer(state);
        applyThinkingPreviewText(state, '');
        scheduleThinkingPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    state.streamSequence += 1;
    state.pendingText = normalizedPreview;
    state.streamWords = words;
    state.streamWordIndex = 0;
    state.streamWordsPerTick = Math.max(1, Math.ceil(words.length / THINKING_PREVIEW_STREAM_MAX_TICKS));
    const firstIndex = Math.min(words.length, state.streamWordsPerTick);
    state.streamWordIndex = firstIndex;
    applyRenderedThinkingPreviewText(state, words.slice(0, firstIndex).join(' '), { syncVisibleAttribute: false });
    if (firstIndex >= words.length) {
        finalizeStreamWithCooldown(state, normalizedPreview, reconcileCheckpoint);
        return;
    }
    scheduleThinkingPreviewStreamTick(state, state.streamSequence, reconcileTick);
};

const reconcileThinkingPreviewCheckpoint = (document: Document, callId: string, reconcileCheckpoint: (documentRef: Document, callId: string) => void, reconcileTick: (documentRef: Document, callId: string) => void): void => {
    const state = getThinkingPreviewState(document, callId);
    if (!state) {
        return;
    }
    const queryElement = state.queryElement;
    if (!queryElement || !queryElement.isConnected) {
        finalizeThinkingPreviewState(state);
        return;
    }
    if (readThinkingPreviewStatus(queryElement) !== 'running') {
        finalizeThinkingPreviewState(state);
        return;
    }
    const nextPreview = stripTrailingPreviewDot(readThinkingPreviewAttribute(queryElement, THINKING_PREVIEW_ATTRIBUTE_NAMES.latest));
    const nowMs = monotonicMs();
    if (state.cooldownUntilMs > nowMs) {
        state.nextCheckpointAt = state.cooldownUntilMs;
        scheduleThinkingPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    state.nextCheckpointAt = nowMs + THINKING_PREVIEW_CHECKPOINT_DELAY_MS;
    if (!nextPreview || nextPreview === state.lastShownPreview || nextPreview === state.pendingText) {
        scheduleThinkingPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    startThinkingPreviewStream(state, nextPreview, reconcileCheckpoint, reconcileTick);
};

const reconcileThinkingPreviewQuery = (queryElement: HTMLElement, reconcileCheckpoint: (documentRef: Document, callId: string) => void, reconcileTick: (documentRef: Document, callId: string) => void): void => {
    const callId = requireThinkingPreviewCallId(queryElement);
    const textElement = requireThinkingPreviewTextElement(queryElement);
    const visiblePreview = stripTrailingPreviewDot(readThinkingPreviewAttribute(queryElement, THINKING_PREVIEW_ATTRIBUTE_NAMES.visible));
    const latestPreview = stripTrailingPreviewDot(readThinkingPreviewAttribute(queryElement, THINKING_PREVIEW_ATTRIBUTE_NAMES.latest));
    const status = readThinkingPreviewStatus(queryElement);
    const documentRef = queryElement.ownerDocument;
    const existing = getThinkingPreviewState(documentRef, callId);
    if (existing) {
        bindThinkingPreviewState(existing, queryElement, textElement);
        if (status === 'running') {
            const nowMs = monotonicMs();
            if (existing.cooldownUntilMs > nowMs) {
                existing.nextCheckpointAt = existing.cooldownUntilMs;
                scheduleThinkingPreviewCheckpoint(existing, reconcileCheckpoint);
                return;
            }
            if (latestPreview && latestPreview !== existing.lastShownPreview && latestPreview !== existing.pendingText) {
                if (updateActiveStreamTarget(existing, latestPreview)) {
                    return;
                }
                if (existing.pendingText !== null) {
                    return;
                }
                existing.nextCheckpointAt = monotonicMs() + THINKING_PREVIEW_CHECKPOINT_DELAY_MS;
                startThinkingPreviewStream(existing, latestPreview, reconcileCheckpoint, reconcileTick);
                return;
            }
            scheduleThinkingPreviewCheckpoint(existing, reconcileCheckpoint);
            return;
        }
        finalizeThinkingPreviewState(existing);
        return;
    }

    const created: ThinkingPreviewState = {
        callId,
        document: documentRef,
        queryElement,
        textElement,
        view: requireThinkingPreviewWindow(queryElement),
        checkpointTimer: null,
        fadeTimer: null,
        nextCheckpointAt: monotonicMs() + THINKING_PREVIEW_CHECKPOINT_DELAY_MS,
        cooldownUntilMs: 0,
        lastShownPreview: visiblePreview,
        renderedPreview: visiblePreview,
        pendingText: null,
        streamSequence: 0,
        streamWords: null,
        streamWordIndex: 0,
        streamWordsPerTick: 1
    };
    setThinkingPreviewState(created);
    bindThinkingPreviewState(created, queryElement, textElement);
    if (status === 'running') {
        if (latestPreview && latestPreview !== created.lastShownPreview) {
            created.nextCheckpointAt = monotonicMs() + THINKING_PREVIEW_CHECKPOINT_DELAY_MS;
            startThinkingPreviewStream(created, latestPreview, reconcileCheckpoint, reconcileTick);
            return;
        }
        scheduleThinkingPreviewCheckpoint(created, reconcileCheckpoint);
        return;
    }
    finalizeThinkingPreviewState(created);
};

export { reconcileThinkingPreviewCheckpoint, reconcileThinkingPreviewQuery, reconcileThinkingPreviewStreamTick };
