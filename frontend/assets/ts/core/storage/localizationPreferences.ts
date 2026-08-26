/* SoAI - Shared frontend storage localization preferences [frontend/assets/ts/core/storage/localizationPreferences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setLocalizationPreferencesSnapshot, type LocalizationPreferences } from '@core/localization/public.ts';
import type { UiPreferences } from '@core/storage/types.ts';

const createLocalizationPreferencesFromUi = (ui: UiPreferences): LocalizationPreferences => ({
    language: ui.language,
    clockFormat: ui.clockFormat,
    regionalLocale: ui.regionalLocale,
    dateFormat: ui.dateFormat,
    measurementUnits: ui.measurementUnits
});

const syncLocalizationPreferencesFromUi = (ui: UiPreferences, options: { dispatch?: boolean } = {}): void => {
    setLocalizationPreferencesSnapshot(createLocalizationPreferencesFromUi(ui), options);
};

export { createLocalizationPreferencesFromUi, syncLocalizationPreferencesFromUi };
