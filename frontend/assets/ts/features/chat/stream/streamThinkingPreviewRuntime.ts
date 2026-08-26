/* SoAI - Chat feature stream thinking preview runtime [frontend/assets/ts/features/chat/stream/streamThinkingPreviewRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { disposeThinkingPreviewRuntime, getThinkingPreviewState, getThinkingPreviewStateCallIds, getThinkingPreviewStateCount } from '@features/chat/stream/thinkingPreviewStateStore.ts';
import { resolveThinkingPreviewElement, THINKING_PREVIEW_SELECTOR } from '@features/chat/stream/thinkingpreviewruntime/dom.ts';
import { finalizeThinkingPreviewState } from '@features/chat/stream/thinkingpreviewruntime/stateTransitions.ts';
import { reconcileThinkingPreviewCheckpoint, reconcileThinkingPreviewQuery, reconcileThinkingPreviewStreamTick } from '@features/chat/stream/thinkingpreviewruntime/runtime.ts';

const pruneDisconnectedStates = (documentRef: Document): void => {
    const callIds = getThinkingPreviewStateCallIds(documentRef);
    if (callIds.length <= 0) {
        return;
    }
    for (const callId of callIds) {
        const state = getThinkingPreviewState(documentRef, callId);
        if (!state) {
            continue;
        }
        const queryElement = state.queryElement;
        if (!queryElement || !queryElement.isConnected) {
            finalizeThinkingPreviewState(state);
        }
    }
};

const resolveThinkingPreviewTargets = (root: Element): readonly HTMLElement[] => {
    if (!(root instanceof HTMLElement)) {
        return [];
    }
    if (root.getAttribute('data-thinking-preview') === 'true') {
        return [root];
    }
    if (root.classList.contains('inline-activity-type-thinking') && root.getAttribute('data-call-id')) {
        const queryElement = resolveThinkingPreviewElement(root);
        return queryElement ? [queryElement] : [];
    }
    const closestThinkingActivity = root.closest('.inline-activity-type-thinking[data-call-id]');
    if (closestThinkingActivity instanceof HTMLElement) {
        const queryElement = resolveThinkingPreviewElement(closestThinkingActivity);
        return queryElement ? [queryElement] : [];
    }
    const results: HTMLElement[] = [];
    for (const queryElement of dom.resolveAll(THINKING_PREVIEW_SELECTOR, root)) {
        if (queryElement instanceof HTMLElement) {
            results.push(queryElement);
        }
    }
    return results;
};

const reconcileThinkingPreviewSubtree = (root: Element | null): void => {
    if (!(root instanceof Element)) {
        return;
    }
    pruneDisconnectedStates(root.ownerDocument);
    const reconcileCheckpoint = (documentRef: Document, callId: string): void => {
        reconcileThinkingPreviewCheckpoint(documentRef, callId, reconcileCheckpoint, reconcileTick);
    };
    const reconcileTick = (documentRef: Document, callId: string): void => {
        reconcileThinkingPreviewStreamTick(documentRef, callId, reconcileCheckpoint, reconcileTick);
    };
    for (const queryElement of resolveThinkingPreviewTargets(root)) {
        reconcileThinkingPreviewQuery(queryElement, reconcileCheckpoint, reconcileTick);
    }
};

export { disposeThinkingPreviewRuntime, reconcileThinkingPreviewSubtree };

export const getThinkingPreviewRuntimeStateCount = (documentRef: Document): number => getThinkingPreviewStateCount(documentRef);
