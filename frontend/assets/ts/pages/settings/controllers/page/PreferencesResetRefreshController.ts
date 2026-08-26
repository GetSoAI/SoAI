/* SoAI - Settings page preferences reset refresh controller [frontend/assets/ts/pages/settings/controllers/page/PreferencesResetRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createUiPrefsSnapshot } from '@pages/settings/controllers/page/loadDataMappers.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { setupManagersEventListeners } from '@pages/settings/controllers/page/service.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { filterSettings, renderAllContent } from '@pages/settings/controllers/page/view.ts';

type PreferencesResetRefreshDependencies = {
    rebindConfigForm: () => void;
    notifySaveChanged: () => void;
};

const PreferencesResetRefreshController = async (page: SettingsRuntimeContext, state: SettingsPageState, dependencies: PreferencesResetRefreshDependencies): Promise<void> => {
    if (page.controls.isDestroyed()) {
        return;
    }
    const uiPrefsManager = state.uiPrefsManager;
    if (!uiPrefsManager) {
        throw new Error('uiPrefsManager not initialized');
    }
    const storageLanguage = page.owners.storage.getLanguage().trim();
    if (!storageLanguage) {
        throw new TypeError('Storage language must be a non-empty string');
    }
    if (storageLanguage !== page.owners.languageService.getLanguage()) {
        await page.owners.languageService.setLanguage(storageLanguage);
    }
    if (page.controls.isDestroyed()) {
        return;
    }

    uiPrefsManager.initialize(createUiPrefsSnapshot(page));

    renderAllContent(page, state);
    dependencies.rebindConfigForm();
    setupManagersEventListeners(page, state);

    filterSettings(page, state);
    dependencies.notifySaveChanged();
};

export { PreferencesResetRefreshController };
export type { PreferencesResetRefreshDependencies };
