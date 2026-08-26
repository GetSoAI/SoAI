/* SoAI - Frontend application theme [frontend/assets/ts/app/bootstrap/stages/theme.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { Theme, ThemePreference } from '@app/bootstrap/stages/types.ts';
import { getEventHub, getMatchMedia, requireDocument } from '@core/environment/public.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';

interface StorageThemeService {
    getTheme: () => string | null;
}

const isStorageThemeService = <T>(value: T): value is T & StorageThemeService => isObject(value) && 'getTheme' in value && isFunction(value.getTheme);

const requireStorageThemeService = (): StorageThemeService => {
    const candidate = requireStorageService();
    if (!isStorageThemeService(candidate)) {
        throw new Error('Theme stage requires core.storage.getTheme()');
    }
    return candidate;
};

const resolveThemePreference = (preference: ThemePreference): Theme => {
    if (preference === 'light' || preference === 'dark') {
        return preference;
    }
    const isDark = getMatchMedia()('(prefers-color-scheme: dark)').matches;
    return isDark ? 'dark' : 'light';
};

const resolveTheme = (preference: string | null): Theme => {
    if (!isString(preference)) {
        throw new Error('Theme preference must be a string');
    }
    const normalized = preference.trim();
    if (normalized !== 'auto' && normalized !== 'light' && normalized !== 'dark') {
        throw new Error(`Unsupported theme preference: ${preference}`);
    }
    return resolveThemePreference(normalized);
};

const applyRootTheme = (theme: Theme): void => {
    const root = requireDocument().documentElement;
    if (!root) {
        throw new Error('Document element must be available to apply theme');
    }
    root.classList.remove('theme-dark', 'theme-light');
    root.classList.add(`theme-${theme}`);
};

const applyBodyTheme = (theme: Theme): void => {
    const doc = requireDocument();
    const body = doc.body;
    if (!body) {
        throw new Error('Document body must be available to apply theme');
    }
    body.classList.remove('theme-dark', 'theme-light');
    body.classList.add(`theme-${theme}`);
};

const applyTheme = (): Theme => {
    const theme = resolveTheme(requireStorageThemeService().getTheme());
    applyRootTheme(theme);
    applyBodyTheme(theme);
    return theme;
};

let storageListenersAttached = false;
const attachStorageThemeListeners = (): void => {
    if (storageListenersAttached) {
        return;
    }
    const handleSoaiStorageReady = (): void => {
        applyTheme();
    };
    getEventHub().addEventListener('soai:storage:ready', handleSoaiStorageReady);
    storageListenersAttached = true;
};

export { applyTheme, attachStorageThemeListeners };
