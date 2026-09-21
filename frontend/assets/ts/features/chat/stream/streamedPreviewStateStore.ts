/* SoAI - Chat feature streamed preview state store [frontend/assets/ts/features/chat/stream/streamedPreviewStateStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clearFadingTextTimers } from '@features/chat/stream/fadingTextScheduler.ts';
import { createDocumentScopedStringKeyMap } from '@core/dom/documentScopedStringKeyMap.ts';

interface StreamedPreviewState {
    key: string;
    document: Document;
    queryElement: HTMLElement | null;
    textElement: HTMLElement | null;
    view: Window | null;
    checkpointTimer: number | null;
    fadeTimer: number | null;
    nextCheckpointAt: number;
    cooldownUntilMs: number;
    lastShownPreview: string;
    renderedPreview: string;
    pendingText: string | null;
    streamSequence: number;
    streamWords: string[] | null;
    streamWordIndex: number;
    streamWordsPerTick: number;
}

const stateByDocument = createDocumentScopedStringKeyMap<StreamedPreviewState>();

const getStreamedPreviewState = (document: Document, key: string): StreamedPreviewState | null => {
    return stateByDocument.get(document, key);
};

const setStreamedPreviewState = (state: StreamedPreviewState): void => {
    stateByDocument.set(state.document, state.key, state);
};

const deleteStreamedPreviewState = (document: Document, key: string): void => {
    stateByDocument.delete(document, key);
};

const clearStreamedPreviewTimers = (state: StreamedPreviewState): void => {
    clearFadingTextTimers(state);
};

const disposeStreamedPreviewRuntime = (document: Document): void => {
    const stateMap = stateByDocument.getMap(document);
    if (!stateMap) {
        return;
    }
    for (const state of stateMap.values()) {
        clearStreamedPreviewTimers(state);
    }
    stateByDocument.clear(document);
};

const getStreamedPreviewStateCount = (document: Document): number => {
    const stateMap = stateByDocument.getMap(document);
    return stateMap ? stateMap.size : 0;
};

const getStreamedPreviewStateKeys = (document: Document): string[] => {
    const stateMap = stateByDocument.getMap(document);
    if (!stateMap) {
        return [];
    }
    return Array.from(stateMap.keys());
};

export { deleteStreamedPreviewState, disposeStreamedPreviewRuntime, getStreamedPreviewState, setStreamedPreviewState, clearStreamedPreviewTimers, getStreamedPreviewStateKeys, getStreamedPreviewStateCount };
export type { StreamedPreviewState };
