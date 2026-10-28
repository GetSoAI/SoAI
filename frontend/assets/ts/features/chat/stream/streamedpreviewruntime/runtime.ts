/* SoAI - Chat feature runtime [frontend/assets/ts/features/chat/stream/streamedpreviewruntime/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stripTrailingPreviewDot, STREAMED_PREVIEW_ATTRIBUTE_NAMES } from '@features/chat/message/messageview/inlineActivityText.ts';
import { monotonicMs, serverEpochMs } from '@core/time/clock.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { scheduleCheckpointTimer } from '@features/chat/stream/fadingTextScheduler.ts';
import { splitTextIntoWordGroups } from '@features/chat/stream/streamingTextFadeWrap.ts';
import { clearStreamedPreviewTimers, getStreamedPreviewState, setStreamedPreviewState, type StreamedPreviewState } from '@features/chat/stream/streamedPreviewStateStore.ts';
import { applyRenderedStreamedPreviewText, applyStreamedPreviewText, bindStreamedPreviewState, finalizeStreamedPreviewState, resetStreamingBuffer } from '@features/chat/stream/streamedpreviewruntime/stateTransitions.ts';
import { readStreamedPreviewAttribute, readStreamedPreviewRevealAtMs, readStreamedPreviewStatus, requireStreamedPreviewKey, requireStreamedPreviewTextElement, requireStreamedPreviewWindow } from '@features/chat/stream/streamedpreviewruntime/dom.ts';

const STREAMED_PREVIEW_CHECKPOINT_DELAY_MS = 3000;
const STREAMED_PREVIEW_STREAM_TICK_DELAY_MS = 44;
const STREAMED_PREVIEW_STREAM_MAX_TICKS = 24;
const STREAMED_PREVIEW_SENTENCE_COOLDOWN_MS = 4000;
const STREAMED_PREVIEW_CHUNK_GRAPHEMES = 8;

const resolveStreamChunks = (value: string): string[] => {
    const chunks: string[] = [];
    const segmenter = new Intl.Segmenter(undefined, { granularity: 'grapheme' });
    for (const group of splitTextIntoWordGroups(value.trim())) {
        const word = group.trimEnd();
        const whitespace = group.slice(word.length);
        const graphemes = Array.from(segmenter.segment(word), (entry) => entry.segment);
        for (let index = 0; index < graphemes.length; index += STREAMED_PREVIEW_CHUNK_GRAPHEMES) {
            const chunk = graphemes.slice(index, index + STREAMED_PREVIEW_CHUNK_GRAPHEMES).join('');
            chunks.push(index + STREAMED_PREVIEW_CHUNK_GRAPHEMES >= graphemes.length ? chunk + whitespace : chunk);
        }
    }
    return chunks;
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
    if (state.pendingText === null || state.streamChunks === null || state.streamChunkIndex <= 0) {
        return false;
    }
    const normalizedPreview = stripTrailingPreviewDot(nextPreview);
    if (!normalizedPreview || normalizedPreview === state.pendingText) {
        return false;
    }
    const nextChunks = resolveStreamChunks(normalizedPreview);
    if (nextChunks.length <= 0) {
        return false;
    }
    const currentIndex = Math.min(state.streamChunkIndex, state.streamChunks.length);
    if (currentIndex <= 0 || currentIndex > nextChunks.length) {
        return false;
    }
    for (let index = 0; index < currentIndex; index += 1) {
        if (state.streamChunks[index] !== nextChunks[index]) {
            return false;
        }
    }
    state.pendingText = normalizedPreview;
    state.streamChunks = nextChunks;
    state.streamChunksPerTick = Math.max(1, Math.ceil(nextChunks.length / STREAMED_PREVIEW_STREAM_MAX_TICKS));
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
    const chunks = state.streamChunks;
    if (!pendingText || !chunks || chunks.length <= 0) {
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
    const nextIndex = Math.min(chunks.length, state.streamChunkIndex + Math.max(1, state.streamChunksPerTick));
    state.streamChunkIndex = nextIndex;
    applyRenderedStreamedPreviewText(state, chunks.slice(0, nextIndex).join('').trimEnd(), { syncVisibleAttribute: false });
    if (nextIndex >= chunks.length) {
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
    if (isReducedAnimationScope(textElement)) {
        finalizeStreamWithCooldown(state, normalizedPreview, reconcileCheckpoint);
        return;
    }
    const chunks = resolveStreamChunks(normalizedPreview);
    if (chunks.length <= 0) {
        resetStreamingBuffer(state);
        applyStreamedPreviewText(state, '');
        scheduleStreamedPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    state.streamSequence += 1;
    state.pendingText = normalizedPreview;
    state.streamChunks = chunks;
    state.streamChunkIndex = 0;
    state.streamChunksPerTick = Math.max(1, Math.ceil(chunks.length / STREAMED_PREVIEW_STREAM_MAX_TICKS));
    const firstIndex = Math.min(chunks.length, state.streamChunksPerTick);
    state.streamChunkIndex = firstIndex;
    applyRenderedStreamedPreviewText(state, chunks.slice(0, firstIndex).join('').trimEnd(), { syncVisibleAttribute: false });
    if (firstIndex >= chunks.length) {
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

const resolveInitialCooldownUntilMs = (queryElement: HTMLElement): number => {
    const revealAtMs = readStreamedPreviewRevealAtMs(queryElement);
    return revealAtMs === null ? 0 : monotonicMs() + Math.max(0, revealAtMs - serverEpochMs());
};

const createStreamedPreviewState = (key: string, queryElement: HTMLElement, textElement: HTMLElement, visiblePreview: string): StreamedPreviewState => {
    const created: StreamedPreviewState = {
        key,
        document: queryElement.ownerDocument,
        queryElement,
        textElement,
        view: requireStreamedPreviewWindow(queryElement),
        checkpointTimer: null,
        fadeTimer: null,
        nextCheckpointAt: monotonicMs() + STREAMED_PREVIEW_CHECKPOINT_DELAY_MS,
        cooldownUntilMs: resolveInitialCooldownUntilMs(queryElement),
        lastShownPreview: visiblePreview,
        renderedPreview: visiblePreview,
        pendingText: null,
        streamSequence: 0,
        streamChunks: null,
        streamChunkIndex: 0,
        streamChunksPerTick: 1
    };
    setStreamedPreviewState(created);
    return created;
};

const reconcileStreamedPreviewQuery = (queryElement: HTMLElement, reconcileCheckpoint: (documentRef: Document, key: string) => void, reconcileTick: (documentRef: Document, key: string) => void): void => {
    const key = requireStreamedPreviewKey(queryElement);
    const textElement = requireStreamedPreviewTextElement(queryElement);
    const visiblePreview = stripTrailingPreviewDot(readStreamedPreviewAttribute(queryElement, STREAMED_PREVIEW_ATTRIBUTE_NAMES.visible));
    const latestPreview = stripTrailingPreviewDot(readStreamedPreviewAttribute(queryElement, STREAMED_PREVIEW_ATTRIBUTE_NAMES.latest));
    const status = readStreamedPreviewStatus(queryElement);
    const state = getStreamedPreviewState(queryElement.ownerDocument, key) ?? createStreamedPreviewState(key, queryElement, textElement, visiblePreview);
    bindStreamedPreviewState(state, queryElement, textElement);
    if (status !== 'running') {
        finalizeStreamedPreviewState(state);
        return;
    }
    const nowMs = monotonicMs();
    if (state.cooldownUntilMs > nowMs) {
        state.nextCheckpointAt = state.cooldownUntilMs;
        scheduleStreamedPreviewCheckpoint(state, reconcileCheckpoint);
        return;
    }
    if (latestPreview && latestPreview !== state.lastShownPreview && latestPreview !== state.pendingText) {
        if (updateActiveStreamTarget(state, latestPreview)) {
            return;
        }
        if (state.pendingText !== null) {
            return;
        }
        state.nextCheckpointAt = monotonicMs() + STREAMED_PREVIEW_CHECKPOINT_DELAY_MS;
        startStreamedPreviewStream(state, latestPreview, reconcileCheckpoint, reconcileTick);
        return;
    }
    scheduleStreamedPreviewCheckpoint(state, reconcileCheckpoint);
};

export { reconcileStreamedPreviewCheckpoint, reconcileStreamedPreviewQuery, reconcileStreamedPreviewStreamTick };
