/* SoAI - Chat autosave lifecycle ownership [frontend/assets/ts/pages/chat/controllers/chatAutoSaveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ComposerDraftFlushOptions } from '@features/chat/public.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import { CHAT_AUTOSAVE_INTERVAL_MS } from '@pages/chat/contracts/constants.ts';

interface StorageManager {
    saveState(force?: boolean): void;
}

interface ComposerDraftManager {
    flushNow(reason: string, options?: ComposerDraftFlushOptions): Promise<void>;
}

interface TimerHost {
    setTimer(functionValue: () => void, delayMs: number, options?: { repeat?: boolean }): number;
    clearTimer(timer: number): void;
}

interface ChatAutoSavePersistencePort extends PageResourcesOwnerHost {
    getStorageManager(): StorageManager;
    getComposerDraftManager(): ComposerDraftManager | null;
    dom: {
        getDocument(): Document;
    };
    timers: TimerHost;
}

const setupAutoSave = (host: { persistence: ChatAutoSavePersistencePort }): { intervalId: number | null; dispose: () => void } => {
    const save = (): void => host.persistence.getStorageManager().saveState();
    const flushDraft = (reason: string, options: ComposerDraftFlushOptions): void => {
        void host.persistence
            .getComposerDraftManager()
            ?.flushNow(reason, options)
            .catch((error) => {
                errorHandler.warn('ChatPage', 'Failed to flush composer draft during autosave lifecycle', ensureError(error));
            });
    };
    const documentRef = host.persistence.dom.getDocument();
    const windowRef = documentRef.defaultView;
    if (windowRef === null) throw new Error('Chat autosave requires a Window');
    const beforeUnloadCleanup = host.persistence.pageResources.on(windowRef, 'beforeunload', () => {
        save();
        flushDraft('beforeunload', { keepalive: true, immediate: true });
    });
    const pageHideCleanup = host.persistence.pageResources.on(windowRef, 'pagehide', () => {
        save();
        flushDraft('pagehide', { keepalive: true, immediate: true });
    });
    const visibilityCleanup = host.persistence.pageResources.on(documentRef, 'visibilitychange', () => {
        if (documentRef.hidden) {
            save();
            flushDraft('visibilitychange', { keepalive: true, immediate: true });
        }
    });
    const intervalId = host.persistence.timers.setTimer(save, CHAT_AUTOSAVE_INTERVAL_MS, { repeat: true });
    const dispose = (): void => {
        beforeUnloadCleanup();
        pageHideCleanup();
        visibilityCleanup();
        if (intervalId !== null) host.persistence.timers.clearTimer(intervalId);
    };
    return { intervalId, dispose };
};

export { setupAutoSave };
export type { ChatAutoSavePersistencePort, TimerHost };
