/* SoAI - Shared storage localization preferences actions [frontend/assets/ts/core/storage/service/localizationpreferences/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { DateFormatPreference, MeasurementUnitsPreference, RegionalLocalePreference } from '@core/localization/public.ts';
import { isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/storage/guards.ts';
import { syncLocalizationPreferencesFromUi } from '@core/storage/localizationPreferences.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';

const syncLocalizationPreferences = (core: StorageRuntime, options: { dispatch?: boolean } = {}): void => {
    syncLocalizationPreferencesFromUi(core.state.cache.ui, options);
};

const createLocalizationPreferenceMethods = (core: StorageRuntime): { getRegionalLocale: () => RegionalLocalePreference; setRegionalLocale: (locale: RegionalLocalePreference) => void; getDateFormat: () => DateFormatPreference; setDateFormat: (format: DateFormatPreference) => void; getMeasurementUnits: () => MeasurementUnitsPreference; setMeasurementUnits: (units: MeasurementUnitsPreference) => void; syncLocalizationPreferences: (options?: { dispatch?: boolean }) => void } => {
    const state = core.state;

    const getRegionalLocale = (): RegionalLocalePreference => state.cache.ui.regionalLocale;

    const setRegionalLocale = (locale: RegionalLocalePreference): void => {
        if (!isRegionalLocalePreference(locale)) {
            throw new Error('regional_locale must be a supported locale preference');
        }
        if (state.cache.ui.regionalLocale === locale) {
            return;
        }
        state.cache.ui.regionalLocale = locale;
        syncLocalizationPreferences(core);
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const getDateFormat = (): DateFormatPreference => state.cache.ui.dateFormat;

    const setDateFormat = (format: DateFormatPreference): void => {
        if (!isDateFormatPreference(format)) {
            throw new Error('date_format must be a supported date preference');
        }
        if (state.cache.ui.dateFormat === format) {
            return;
        }
        state.cache.ui.dateFormat = format;
        syncLocalizationPreferences(core);
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const getMeasurementUnits = (): MeasurementUnitsPreference => state.cache.ui.measurementUnits;

    const setMeasurementUnits = (units: MeasurementUnitsPreference): void => {
        if (!isMeasurementUnitsPreference(units)) {
            throw new Error('measurement_units must be a supported units preference');
        }
        if (state.cache.ui.measurementUnits === units) {
            return;
        }
        state.cache.ui.measurementUnits = units;
        syncLocalizationPreferences(core);
        terminateHandledPromise(core.queuePersist('ui'));
    };

    return {
        getRegionalLocale,
        setRegionalLocale,
        getDateFormat,
        setDateFormat,
        getMeasurementUnits,
        setMeasurementUnits,
        syncLocalizationPreferences: (options: { dispatch?: boolean } = {}): void => syncLocalizationPreferences(core, options)
    };
};

export { createLocalizationPreferenceMethods, syncLocalizationPreferences };
