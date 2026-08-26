/* SoAI - Shared storage theme state [frontend/assets/ts/core/storage/service/events/sync/themeState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent, getBody, getDocumentElement } from '@core/environment/public.ts';
import type { ThemeType } from '@core/storage/types.ts';

const applyThemeDomState = (actualTheme: string): void => {
    const root = getDocumentElement();
    const body = getBody();

    root.classList.remove('theme-dark', 'theme-light');
    root.classList.add(`theme-${actualTheme}`);
    body.classList.remove('theme-dark', 'theme-light');
    body.classList.add(`theme-${actualTheme}`);
};

const dispatchThemeChanged = (theme: ThemeType, actualTheme: ThemeType): void => {
    dispatchCustomEvent('themeChanged', { theme, actualTheme });
};

const resolveThemePreference = (preference: string, currentTheme: ThemeType): ThemeType => {
    const desiredTheme = preference === 'auto' || preference === 'light' || preference === 'dark' ? preference : currentTheme;

    if (desiredTheme !== 'auto' && desiredTheme !== 'light' && desiredTheme !== 'dark') {
        throw new Error(`Invalid theme value: ${String(preference)}`);
    }

    return desiredTheme;
};

const resolveThemePreferenceFromDom = (themePreference: ThemeType): ThemeType => {
    const root = getDocumentElement();
    const initializeTheme = root.dataset['soaiThemePreference'] || (root.classList.contains('theme-light') ? 'light' : root.classList.contains('theme-dark') ? 'dark' : null);
    if (initializeTheme === 'auto' || initializeTheme === 'light' || initializeTheme === 'dark') {
        return initializeTheme;
    }
    return themePreference;
};

export { applyThemeDomState, dispatchThemeChanged, resolveThemePreference, resolveThemePreferenceFromDom };
