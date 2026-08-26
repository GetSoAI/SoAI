/* SoAI - Character map modal contracts [frontend/assets/ts/pages/chat/controllers/modals/charactermap/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { CharacterMapCatalog } from '@features/chat/public.ts';
import type { CharacterMapViewState } from '@pages/chat/controllers/modals/charactermap/state.ts';

interface CharacterMapModalRefs {
    modal: HTMLElement;
    search: HTMLInputElement;
    searchButton: HTMLButtonElement;
    font: HTMLSelectElement;
    subset: HTMLSelectElement;
    loading: HTMLElement;
    error: HTMLElement;
    retry: HTMLButtonElement;
    empty: HTMLElement;
    grid: HTMLElement;
    status: HTMLElement;
    codePoints: HTMLElement;
    name: HTMLElement;
    staging: HTMLInputElement;
    select: HTMLButtonElement;
    copy: HTMLButtonElement;
    insert: HTMLButtonElement;
}

interface CharacterMapModalHost {
    feedback: Pick<PageFeedback, 'handle' | 'show'>;
    initialViewState: CharacterMapViewState | null;
    loadCatalog(): Promise<CharacterMapCatalog>;
    saveViewState(state: CharacterMapViewState): void;
    insertText(text: string): void;
    closeAfterInsert(): void;
    hasClipboardSupport(): boolean;
    copyToClipboard(text: string, options?: { notify?: (message: string, type: 'success' | 'info' | 'warning' | 'danger' | 'error' | 'copy' | 'refresh' | 'download') => void }): Promise<boolean | void>;
    runTask(operationId: string, task: () => Promise<void> | void): void;
}

export type { CharacterMapModalHost, CharacterMapModalRefs };
