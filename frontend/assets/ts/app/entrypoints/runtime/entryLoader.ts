/* SoAI - Frontend application entry loader [frontend/assets/ts/app/entrypoints/runtime/entryLoader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { EntryName } from '@app/entrypoints/entrypoints.ts';
import { loadEntryDependencies } from '@app/entrypoints/loader.ts';
import type { EntryModule } from '@app/entrypoints/types.ts';
import { getDocumentElement } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { setLanguageRuntime } from '@core/languageservice/runtime.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { ensureError } from '@core/errors/coerce.ts';

type EntryAction = (entryModule: EntryModule) => void | Promise<void>;

const ENTRY_ACTIONS: Readonly<Record<EntryName, EntryAction>> = Object.freeze({
    main: (entryModule: EntryModule) => entryModule.startPrimaryApp(),
    detached: (entryModule: EntryModule) => entryModule.startDetachedWindow()
});

type BootState = 'loading' | 'primed' | 'failed';

const setBootState = (state: BootState | null): void => {
    const root = getDocumentElement();
    if (state === null) {
        errorHandler.debug('EntryLoader', 'setBootState: clearing boot state');
        root.removeAttribute('data-soai-boot-state');
        return;
    }
    errorHandler.debug('EntryLoader', `setBootState: setting boot state to ${state}`);
    root.setAttribute('data-soai-boot-state', state);
};

interface BootstrapOptions {
    entry: string;
}

const isEntryName = (value: string): value is EntryName => value === 'main' || value === 'detached';

export const bootstrapEntry = async ({ entry }: BootstrapOptions): Promise<void> => {
    errorHandler.debug('EntryLoader', '>>> entryLoader: START');
    if (!isEntryName(entry)) {
        throw new Error(`Unsupported entry target "${entry}" supplied to bootstrapEntry`);
    }
    const entryName: EntryName = entry;
    setLanguageRuntime(getLanguageService());
    setBootState('loading');

    errorHandler.debug('EntryLoader', '>>> entryLoader: set state primed');
    setBootState('primed');

    let entryModule: EntryModule;
    try {
        errorHandler.debug('EntryLoader', `>>> entryLoader: loading dependencies for ${entryName}`);
        entryModule = await loadEntryDependencies(entryName);
    } catch (error) {
        setBootState('failed');
        const runtimeError = ensureError(error);
        errorHandler.error('EntryLoader', 'Entry dependency loading failed', runtimeError);
        throw runtimeError;
    }

    const start = ENTRY_ACTIONS[entryName];
    try {
        errorHandler.debug('EntryLoader', '>>> entryLoader: before await start');
        await start(entryModule);
    } catch (error) {
        setBootState('failed');
        throw ensureError(error);
    }
    errorHandler.debug('EntryLoader', '>>> entryLoader: after await start');
    errorHandler.debug('EntryLoader', '>>> entryLoader: clearing boot state');
    setBootState(null);
};
