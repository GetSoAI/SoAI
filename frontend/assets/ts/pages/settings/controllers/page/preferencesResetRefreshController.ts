/* SoAI - Prepared Settings preference reset acknowledgement and projection [frontend/assets/ts/pages/settings/controllers/page/preferencesResetRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError } from '@core/errors/abort.ts';
import { isPresentationOwnerMutationAllowed } from '@core/presentationOwner.ts';
import { createUiPrefsSnapshot } from '@pages/settings/controllers/page/loadDataMappers.ts';
import type { SettingsPreferenceResetType, SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { filterSettings } from '@pages/settings/controllers/page/view.ts';
import { selectAppearanceUiPreferences } from '@pages/settings/controllers/uiprefs/appearancePreferencesDomain.ts';

interface PreferencesResetRefreshDependencies {
    notifySaveChanged: () => void;
}

const preparePreferencesResetRefresh = (page: SettingsRuntimeContext, state: SettingsPageState, dependencies: PreferencesResetRefreshDependencies, type: SettingsPreferenceResetType): (() => Promise<void>) => {
    const manager = state.uiPrefsManager;
    if (!manager) throw new Error('uiPrefsManager not initialized');
    const epoch = page.owners.auth.authEpoch;
    const owner = page.owners.pageContext.presentationOwner;
    const isCurrent = (): boolean => !page.controls.isDestroyed() && page.owners.auth.authEpoch === epoch && state.uiPrefsManager === manager && isPresentationOwnerMutationAllowed(owner);
    const requireCurrent = (): void => {
        if (!isCurrent()) throw createAbortError('Preference reset is no longer current');
    };
    requireCurrent();
    const submitted = manager.currentData;
    const refreshOcr = type === 'preferences' ? state.preferencesManager?.prepareOcrReset() : null;
    return async (): Promise<void> => {
        requireCurrent();
        if (type === 'preferences') {
            const language = page.owners.storage.getLanguage().trim();
            if (!language) throw new TypeError('Storage language must be a non-empty string');
            await page.owners.languageService.setLanguage(language, isCurrent);
            requireCurrent();
            if (!page.owners.languageService.isLanguageRequestSettled(language)) throw createAbortError('Preference reset language was superseded');
        }
        const snapshot = createUiPrefsSnapshot(page);
        manager.commitBaselinePatch(type === 'preferences' ? snapshot : selectAppearanceUiPreferences(snapshot), submitted);
        if (refreshOcr) await refreshOcr();
        requireCurrent();
        state.preferencesManager?.syncUiPreferences();
        state.themeManager?.syncUiPreferences();
        state.dirtyStateManager?.refreshRenderedFields();
        filterSettings(page, state);
        state.preferencesManager?.syncOcrDirtyState();
        dependencies.notifySaveChanged();
        requireCurrent();
    };
};

export { preparePreferencesResetRefresh };
export type { PreferencesResetRefreshDependencies };
