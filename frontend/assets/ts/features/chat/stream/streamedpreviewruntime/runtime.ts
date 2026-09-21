/* SoAI - Chat feature runtime [frontend/assets/ts/features/chat/stream/streamedpreviewruntime/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stripTrailingPreviewDot, STREAMED_PREVIEW_ATTRIBUTE_NAMES } from '@features/chat/message/messageview/inlineActivityText.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { scheduleCheckpointTimer } from '@features/chat/stream/fadingTextScheduler.ts';
import { clearStreamedPreviewTimers, getStreamedPreviewState, setStreamedPreviewState, type StreamedPreviewState } from '@features/chat/stream/streamedPreviewStateStore.ts';
import { applyRenderedStreamedPreviewText, applyStreamedPreviewText, bindStreamedPreviewState, finalizeStreamedPreviewState, resetStreamingBuffer } from '@features/chat/stream/streamedpreviewruntime/stateTransitions.ts';
import { readStreamedPreviewAttribute, readStreamedPreviewStatus, requireStreamedPreviewKey, requireStreamedPreviewTextElement, requireStreamedPreviewWindow } from '@features/chat/stream/streamedpreviewruntime/dom.ts';

const STREAMED_PREVIEW_CHECKPOINT_DELAY_MS = 3000;
const STREAMED_PREVIEW_STREAM_TICK_DELAY_MS = 44;
const STREAMED_PREVIEW_STREAM_MAX_TICKS = 24;
const STREAMED_PREVIEW_SENTENCE_COOLDOWN_MS = 4000;

const resolveWords = (value: string): string[] => {
    const trimmed = value.trim();
    return trimmed ? trimmed.split(/\s+/g) : [];
};

const scheduleCooldown = (state: StreamedPreviewState): void => {
    state.cooldownUntilMs = monotonicMs() + STREAMED_PREVIEW_SENTENCE_COOLDOWN_MS;
};

const applyPendingPreviewAndScheduleCheckpoint = (state: StreamedPreviewState, pendingText: string, reconcileCheckpoint: (documentRef: Document, key: string) => void): void => {
    resetStreamingBuffer(state);
    applyStreamedPreviewText(state, pendingText);
    scheduleStreamedPreviewCheckpoint(state, reconcileCheckpoint);
};

const finalizeStreamWithCooldown = (state: StreamedPreviewState, pendingText: string, reconcileCheckpoint: (documentRef: Document, key: string) => void): void => {
    resetStreamingBuffer(state);
    applyStreamedPreviewText(state, pendingText);
    scheduleCooldown(state);
    state.nextCheckpointAt = state.cooldownUntilMs;
    scheduleStreamedPreviewCheckpoint(state, reconcileCheckpoint);
};

const updateActiveStreamTarget = (state: StreamedPreviewState, nextPreview: string): boolean => {
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
    state.streamWordsPerTick = Math.max(1, Math.ceil(nextWords.length / STREAMED_PREVIEW_STREAM_MAX_TICKS));
    return true;
};

const scheduleStreamedPreviewCheckpoint = (state: StreamedPreviewState, reconcileCheckpoint: (documentRef: Document, key: string) => void): void => {
    const queryElement = state.queryElement;
    if (!queryElement || !queryElement.isConnected) {
        finalizeStreamedPreviewState(state);
        return;
    }
    if (readStreamedPreviewStatus(queryElement) !== 'running') {
        return;
    }
    state.view = requireStreamedPreviewWindow(queryElement);
    if (state.cooldownUntilMs > 0) {
        state.nextCheckpointAt = Math.max(state.nextCheckpointAt, state.cooldownUntilMs);
    }
    scheduleCheckpointTimer(state, () => {
        reconcileCheckpoint(state.document, state.key);
    });
};

const scheduleStreamedPreviewStreamTick = (state: StreamedPreviewState, expectedSequence: number, reconcileTick: (documentRef: Document, key: string) => void): void => {
    const queryElement = state.queryElement;
    const view = state.view;
    if (!queryElement || !queryElement.isConnected || !view) {
        return;
    }
    if (state.fadeTimer !== null) {
        return;
    }
    const documentRef = state.document;
    const key = state.key;
    state.fadeTimer = view.setTimeout((): void => {
        const currentState = getStreamedPreviewState(documentRef, key);
        if (!currentState) {
            return;
        }
        currentState.fadeTimer = null;
        if (currentState.streamSequence !== expectedSequence) {
            return;
        }
        reconcileTick(documentRef, key);
    }, STREAMED_PREVIEW_STREAM_TICK_DELAY_MS);
};

const reconcileStreamedPreviewStreamTick = (documentRef: Document, key: string, reconcileCheckpoint: (documentRef: Document, key: string) => void, reconcileTick: (documentRef: Document, key: string) => void): void => {
    const state = getStreamedPreviewState(documentRef, key);
    if (!state) {
        return;
    }
    const queryElement = state.queryElement;
    const textElement = state.textElement;
    const pendingText = state.pendingText;
    const words = state.streamWords;
    if (!pendingText || !words || words.length <= 0) {
        scheduleStreamedPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    if (!queryElement || !textElement || !queryElement.isConnected || !textElement.isConnected) {
        finalizeStreamedPreviewState(state);
        return;
    }
    if (readStreamedPreviewStatus(queryElement) !== 'running') {
        resetStreamingBuffer(state);
        applyStreamedPreviewText(state, pendingText);
        finalizeStreamedPreviewState(state);
        return;
    }
    const nextIndex = Math.min(words.length, state.streamWordIndex + Math.max(1, state.streamWordsPerTick));
    state.streamWordIndex = nextIndex;
    applyRenderedStreamedPreviewText(state, words.slice(0, nextIndex).join(' '), { syncVisibleAttribute: false });
    if (nextIndex >= words.length) {
        finalizeStreamWithCooldown(state, pendingText, reconcileCheckpoint);
        return;
    }
    scheduleStreamedPreviewStreamTick(state, state.streamSequence, reconcileTick);
};

const startStreamedPreviewStream = (state: StreamedPreviewState, nextPreview: string, reconcileCheckpoint: (documentRef: Document, key: string) => void, reconcileTick: (documentRef: Document, key: string) => void): void => {
    const queryElement = state.queryElement;
    const textElement = state.textElement;
    if (!queryElement || !textElement || !queryElement.isConnected || !textElement.isConnected) {
        applyPendingPreviewAndScheduleCheckpoint(state, nextPreview, reconcileCheckpoint);
        return;
    }
    clearStreamedPreviewTimers(state);
    state.view = requireStreamedPreviewWindow(queryElement);
    const normalizedPreview = stripTrailingPreviewDot(nextPreview);
    const words = resolveWords(normalizedPreview);
    if (words.length <= 0) {
        resetStreamingBuffer(state);
        applyStreamedPreviewText(state, '');
        scheduleStreamedPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    state.streamSequence += 1;
    state.pendingText = normalizedPreview;
    state.streamWords = words;
    state.streamWordIndex = 0;
    state.streamWordsPerTick = Math.max(1, Math.ceil(words.length / STREAMED_PREVIEW_STREAM_MAX_TICKS));
    const firstIndex = Math.min(words.length, state.streamWordsPerTick);
    state.streamWordIndex = firstIndex;
    applyRenderedStreamedPreviewText(state, words.slice(0, firstIndex).join(' '), { syncVisibleAttribute: false });
    if (firstIndex >= words.length) {
        finalizeStreamWithCooldown(state, normalizedPreview, reconcileCheckpoint);
        return;
    }
    scheduleStreamedPreviewStreamTick(state, state.streamSequence, reconcileTick);
};

const reconcileStreamedPreviewCheckpoint = (document: Document, key: string, reconcileCheckpoint: (documentRef: Document, key: string) => void, reconcileTick: (documentRef: Document, key: string) => void): void => {
    const state = getStreamedPreviewState(document, key);
    if (!state) {
        return;
    }
    const queryElement = state.queryElement;
    if (!queryElement || !queryElement.isConnected) {
        finalizeStreamedPreviewState(state);
        return;
    }
    if (readStreamedPreviewStatus(queryElement) !== 'running') {
        finalizeStreamedPreviewState(state);
        return;
    }
    const nextPreview = stripTrailingPreviewDot(readStreamedPreviewAttribute(queryElement, STREAMED_PREVIEW_ATTRIBUTE_NAMES.latest));
    const nowMs = monotonicMs();
    if (state.cooldownUntilMs > nowMs) {
        state.nextCheckpointAt = state.cooldownUntilMs;
        scheduleStreamedPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    state.nextCheckpointAt = nowMs + STREAMED_PREVIEW_CHECKPOINT_DELAY_MS;
    if (!nextPreview || nextPreview === state.lastShownPreview || nextPreview === state.pendingText) {
        scheduleStreamedPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    startStreamedPreviewStream(state, nextPreview, reconcileCheckpoint, reconcileTick);
};

const reconcileStreamedPreviewQuery = (queryElement: HTMLElement, reconcileCheckpoint: (documentRef: Document, key: string) => void, reconcileTick: (documentRef: Document, key: string) => void): void => {
    const key = requireStreamedPreviewKey(queryElement);
    const textElement = requireStreamedPreviewTextElement(queryElement);
    const visiblePreview = stripTrailingPreviewDot(readStreamedPreviewAttribute(queryElement, STREAMED_PREVIEW_ATTRIBUTE_NAMES.visible));
    const latestPreview = stripTrailingPreviewDot(readStreamedPreviewAttribute(queryElement, STREAMED_PREVIEW_ATTRIBUTE_NAMES.latest));
    const status = readStreamedPreviewStatus(queryElement);
    const documentRef = queryElement.ownerDocument;
    const existing = getStreamedPreviewState(documentRef, key);
    if (existing) {
        bindStreamedPreviewState(existing, queryElement, textElement);
        if (status === 'running') {
            const nowMs = monotonicMs();
            if (existing.cooldownUntilMs > nowMs) {
                existing.nextCheckpointAt = existing.cooldownUntilMs;
                scheduleStreamedPreviewCheckpoint(existing, reconcileCheckpoint);
                return;
            }
            if (latestPreview && latestPreview !== existing.lastShownPreview && latestPreview !== existing.pendingText) {
                if (updateActiveStreamTarget(existing, latestPreview)) {
                    return;
                }
                if (existing.pendingText !== null) {
                    return;
                }
                existing.nextCheckpointAt = monotonicMs() + STREAMED_PREVIEW_CHECKPOINT_DELAY_MS;
                startStreamedPreviewStream(existing, latestPreview, reconcileCheckpoint, reconcileTick);
                return;
            }
            scheduleStreamedPreviewCheckpoint(existing, reconcileCheckpoint);
            return;
        }
        finalizeStreamedPreviewState(existing);
        return;
    }

    const created: StreamedPreviewState = {
        key,
        document: documentRef,
        queryElement,
        textElement,
        view: requireStreamedPreviewWindow(queryElement),
        checkpointTimer: null,
        fadeTimer: null,
        nextCheckpointAt: monotonicMs() + STREAMED_PREVIEW_CHECKPOINT_DELAY_MS,
        cooldownUntilMs: 0,
        lastShownPreview: visiblePreview,
        renderedPreview: visiblePreview,
        pendingText: null,
        streamSequence: 0,
        streamWords: null,
        streamWordIndex: 0,
        streamWordsPerTick: 1
    };
    setStreamedPreviewState(created);
    bindStreamedPreviewState(created, queryElement, textElement);
    if (status === 'running') {
        if (latestPreview && latestPreview !== created.lastShownPreview) {
            created.nextCheckpointAt = monotonicMs() + STREAMED_PREVIEW_CHECKPOINT_DELAY_MS;
            startStreamedPreviewStream(created, latestPreview, reconcileCheckpoint, reconcileTick);
            return;
        }
        scheduleStreamedPreviewCheckpoint(created, reconcileCheckpoint);
        return;
    }
    finalizeStreamedPreviewState(created);
};

export { reconcileStreamedPreviewCheckpoint, reconcileStreamedPreviewQuery, reconcileStreamedPreviewStreamTick };
