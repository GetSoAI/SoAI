/* SoAI - Shared storage merge remote preferences contracts [frontend/assets/ts/core/storage/persistence/mergeremotepreferences/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatCache, ChatPreferencesManager, HardwareCache, LogsCache, ModalState, StorageCache, TerminalCache, UiPreferences } from '@core/storage/types.ts';

interface ThemeApplyOptions {
    persist?: boolean | undefined;
    update?: boolean | undefined;
}

interface MergeRemoteContext {
    cache: StorageCache;
    defaults: StorageCache;
    localStorageGroups: ReadonlyArray<string>;
    internalRemoteKeys: ReadonlySet<string>;
    persistedGroupKeys: ReadonlyArray<string>;
    createDefaults: () => StorageCache;
    clone: <T>(value: T) => T;
    normalizeZoom: (zoom: number, min: number, max: number) => number;
    normalizeLimit: (limit: number) => number;
    updatePersisted: (group: string) => void;
    syncLocal: (group: string) => void;
    applyTheme: (preference: string, options?: ThemeApplyOptions) => string;
    bodyClass: (className: string, enabled: boolean) => void;
    setGlassDisabled: (disabled: boolean) => void;
    setAttr: (name: string, value: string) => void;
    ensureMainState: () => void;
}

export type { ChatCache, ChatPreferencesManager, HardwareCache, LogsCache, MergeRemoteContext, ModalState, StorageCache, TerminalCache, ThemeApplyOptions, UiPreferences };
