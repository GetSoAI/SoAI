/* SoAI - Chat feature stream message spinner status runtime [frontend/assets/ts/features/chat/stream/streamMessageSpinnerStatusRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { STATUS_SELECTOR } from '@features/chat/stream/streamMessageSpinnerStatusDom.ts';
import { reconcileStreamingSpinnerStatusElement } from '@features/chat/stream/streamMessageSpinnerStatusElementReconcile.ts';
import { clearRuntimeStateByDocument, getRuntimeStateByMessageIdMap } from '@features/chat/stream/streamMessageSpinnerStatusState.ts';
import { finalizeState } from '@features/chat/stream/streamMessageSpinnerStatusRuntimeTransition.ts';
import { resolveMessageActionsElement, resolveStreamingStatusElement } from '@features/chat/stream/streamMessageSpinnerStatusDomPolicy.ts';

const pruneDisconnectedStates = (documentRef: Document): void => {
    const runtimeStateByMessageId = getRuntimeStateByMessageIdMap(documentRef);
    for (const state of runtimeStateByMessageId.values()) {
        const messageRoot = state.messageRoot;
        if (!messageRoot || !messageRoot.isConnected) {
            finalizeState(documentRef, state);
        }
    }
};

const resolveStatusElementFromMessageRoot = (messageRoot: HTMLElement): HTMLElement | null => {
    const actionsElement = resolveMessageActionsElement(messageRoot);
    if (!(actionsElement instanceof HTMLElement)) {
        return null;
    }
    return resolveStreamingStatusElement(actionsElement);
};

const resolveStatusTargets = (root: Element): readonly HTMLElement[] => {
    if (!(root instanceof HTMLElement)) {
        return [];
    }
    if (root.getAttribute('data-stream-spinner-status') === 'true') {
        return [root];
    }
    if (root.classList.contains('chat-message')) {
        const statusElement = resolveStatusElementFromMessageRoot(root);
        return statusElement ? [statusElement] : [];
    }
    const closestMessageRoot = root.closest('.chat-message');
    if (closestMessageRoot instanceof HTMLElement) {
        const statusElement = resolveStatusElementFromMessageRoot(closestMessageRoot);
        return statusElement ? [statusElement] : [];
    }
    const results: HTMLElement[] = [];
    for (const statusElement of dom.resolveAll(STATUS_SELECTOR, root)) {
        if (statusElement instanceof HTMLElement) {
            results.push(statusElement);
        }
    }
    return results;
};

const reconcileStreamingSpinnerStatusSubtree = (root: Element | null): void => {
    if (!(root instanceof Element)) {
        return;
    }
    const documentRef = root.ownerDocument;
    pruneDisconnectedStates(documentRef);
    for (const statusElement of resolveStatusTargets(root)) {
        reconcileStreamingSpinnerStatusElement({ documentRef, statusElement });
    }
};

const disposeStreamingSpinnerStatusRuntime = (documentRef: Document): void => {
    const runtimeStateByMessageId = getRuntimeStateByMessageIdMap(documentRef);
    for (const state of Array.from(runtimeStateByMessageId.values())) {
        finalizeState(documentRef, state);
    }
    clearRuntimeStateByDocument(documentRef);
};

export { disposeStreamingSpinnerStatusRuntime, reconcileStreamingSpinnerStatusSubtree };
