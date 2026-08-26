/* SoAI - Overlays feature restart effects [frontend/assets/ts/features/overlays/restart/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { RESTART_CACHE_TTL_MS, shouldPersistRestartOperation } from '@features/overlays/restart/constants.ts';
import type { OverlayElements, RestartOperationState, RestartSessionRepository } from '@features/overlays/restart/types.ts';

interface OverlayVisibilityOptions {
    elements: OverlayElements;
    addClassName: (element: HTMLElement, className: string) => void;
    removeClassName: (element: HTMLElement, className: string) => void;
    setHidden: boolean;
}

interface RestoreOverlaySessionOptions {
    repository: RestartSessionRepository;
    showOperation: (state: RestartOperationState) => void;
    setCurrentRetry: (retryCount: number) => void;
}

const readRestorableRestartState = (repository: RestartSessionRepository): RestartOperationState | null => {
    const cachedState = repository.read();
    if (!cachedState) {
        return null;
    }

    const isFresh = Date.now() - cachedState.timestamp < RESTART_CACHE_TTL_MS;
    if (isFresh && shouldPersistRestartOperation(cachedState.type)) {
        return cachedState;
    }

    repository.clear();
    return null;
};

const restoreRestartOverlaySession = ({ repository, showOperation, setCurrentRetry }: RestoreOverlaySessionOptions): void => {
    const cachedState = readRestorableRestartState(repository);
    if (!cachedState) {
        return;
    }
    showOperation(cachedState);
    setCurrentRetry(cachedState.retry);
};

const setRestartOverlayVisibility = ({ elements, addClassName, removeClassName, setHidden }: OverlayVisibilityOptions): void => {
    const { overlay } = elements;
    if (!overlay) return;

    if (setHidden) {
        addClassName(overlay, 'u-hidden');
        overlay.setAttribute('hidden', 'true');
        overlay.setAttribute('aria-hidden', 'true');
        return;
    }

    removeClassName(overlay, 'u-hidden');
    overlay.removeAttribute('hidden');
    overlay.setAttribute('aria-hidden', 'false');
};

export { readRestorableRestartState, restoreRestartOverlaySession, setRestartOverlayVisibility };
