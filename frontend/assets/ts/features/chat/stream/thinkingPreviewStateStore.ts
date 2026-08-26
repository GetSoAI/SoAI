/* SoAI - Chat feature thinking preview state store [frontend/assets/ts/features/chat/stream/thinkingPreviewStateStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clearFadingTextTimers } from '@features/chat/stream/fadingTextScheduler.ts';
import { createDocumentScopedStringKeyMap } from '@core/dom/documentScopedStringKeyMap.ts';

interface ThinkingPreviewState {
    callId: string;
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

const stateByDocument = createDocumentScopedStringKeyMap<ThinkingPreviewState>();

const getThinkingPreviewState = (document: Document, callId: string): ThinkingPreviewState | null => {
    return stateByDocument.get(document, callId);
};

const setThinkingPreviewState = (state: ThinkingPreviewState): void => {
    stateByDocument.set(state.document, state.callId, state);
};

const deleteThinkingPreviewState = (document: Document, callId: string): void => {
    stateByDocument.delete(document, callId);
};

const clearThinkingPreviewTimers = (state: ThinkingPreviewState): void => {
    clearFadingTextTimers(state);
};

const disposeThinkingPreviewRuntime = (document: Document): void => {
    const stateMap = stateByDocument.getMap(document);
    if (!stateMap) {
        return;
    }
    for (const state of stateMap.values()) {
        clearThinkingPreviewTimers(state);
    }
    stateByDocument.clear(document);
};

const getThinkingPreviewStateCount = (document: Document): number => {
    const stateMap = stateByDocument.getMap(document);
    return stateMap ? stateMap.size : 0;
};

const getThinkingPreviewStateCallIds = (document: Document): string[] => {
    const stateMap = stateByDocument.getMap(document);
    if (!stateMap) {
        return [];
    }
    return Array.from(stateMap.keys());
};

export { deleteThinkingPreviewState, disposeThinkingPreviewRuntime, getThinkingPreviewState, setThinkingPreviewState, clearThinkingPreviewTimers, getThinkingPreviewStateCallIds, getThinkingPreviewStateCount };
export type { ThinkingPreviewState };
