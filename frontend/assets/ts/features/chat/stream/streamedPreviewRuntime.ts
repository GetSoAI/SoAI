/* SoAI - Chat feature streamed preview runtime [frontend/assets/ts/features/chat/stream/streamedPreviewRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { STREAMED_PREVIEW_ATTRIBUTE_NAMES } from '@features/chat/message/messageview/inlineActivityText.ts';
import { disposeStreamedPreviewRuntime, getStreamedPreviewState, getStreamedPreviewStateCount, getStreamedPreviewStateKeys } from '@features/chat/stream/streamedPreviewStateStore.ts';
import { resolveStreamedPreviewElement, STREAMED_PREVIEW_OWNER_SELECTOR, STREAMED_PREVIEW_SELECTOR } from '@features/chat/stream/streamedpreviewruntime/dom.ts';
import { finalizeStreamedPreviewState } from '@features/chat/stream/streamedpreviewruntime/stateTransitions.ts';
import { reconcileStreamedPreviewCheckpoint, reconcileStreamedPreviewQuery, reconcileStreamedPreviewStreamTick } from '@features/chat/stream/streamedpreviewruntime/runtime.ts';

const pruneDisconnectedStates = (documentRef: Document): void => {
    const keys = getStreamedPreviewStateKeys(documentRef);
    if (keys.length <= 0) {
        return;
    }
    for (const key of keys) {
        const state = getStreamedPreviewState(documentRef, key);
        if (!state) {
            continue;
        }
        const queryElement = state.queryElement;
        if (!queryElement || !queryElement.isConnected) {
            finalizeStreamedPreviewState(state);
        }
    }
};

const resolveStreamedPreviewTargets = (root: Element): readonly HTMLElement[] => {
    if (!(root instanceof HTMLElement)) {
        return [];
    }
    if (root.getAttribute(STREAMED_PREVIEW_ATTRIBUTE_NAMES.root) === 'true') {
        return [root];
    }
    const owner = root.closest(STREAMED_PREVIEW_OWNER_SELECTOR);
    if (owner instanceof HTMLElement) {
        const queryElement = resolveStreamedPreviewElement(owner);
        return queryElement ? [queryElement] : [];
    }
    const results: HTMLElement[] = [];
    for (const queryElement of dom.resolveAll(STREAMED_PREVIEW_SELECTOR, root)) {
        if (queryElement instanceof HTMLElement) {
            results.push(queryElement);
        }
    }
    return results;
};

const reconcileStreamedPreviewSubtree = (root: Element | null): void => {
    if (!(root instanceof Element)) {
        return;
    }
    pruneDisconnectedStates(root.ownerDocument);
    const reconcileCheckpoint = (documentRef: Document, key: string): void => {
        reconcileStreamedPreviewCheckpoint(documentRef, key, reconcileCheckpoint, reconcileTick);
    };
    const reconcileTick = (documentRef: Document, key: string): void => {
        reconcileStreamedPreviewStreamTick(documentRef, key, reconcileCheckpoint, reconcileTick);
    };
    for (const queryElement of resolveStreamedPreviewTargets(root)) {
        reconcileStreamedPreviewQuery(queryElement, reconcileCheckpoint, reconcileTick);
    }
};

export { disposeStreamedPreviewRuntime, reconcileStreamedPreviewSubtree };

export const getStreamedPreviewRuntimeStateCount = (documentRef: Document): number => getStreamedPreviewStateCount(documentRef);
