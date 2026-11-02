/* SoAI - Native Settings preference control binding and incremental projection [frontend/assets/ts/pages/settings/controllers/preferences/preferenceControlsDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { requireClosestElement } from '@core/dom/attributes.ts';
import { readFiniteInputValueOrNull } from '@core/dom/formValues.ts';
import { narrowInput, narrowSelect } from '@core/dom/narrowElement.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/localization/public.ts';
import { setSettingItemApplicable } from '@core/settings/settingItemApplicability.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { syncFlagSelect } from '@core/ui/dropdown/flagSelect.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { createPreferenceSliderDefinitions } from '@pages/settings/controllers/preferences/preferenceSlidersDomain.ts';
import { createPreferenceToggleDefinitions } from '@pages/settings/controllers/preferences/toggles.ts';
import type { PreferencesManagerHost } from '@pages/settings/controllers/preferences/types.ts';
import { requireUiPrefsClockFormat, requireUiPrefsDateFormat, requireUiPrefsLanguage, requireUiPrefsMeasurementUnits, requireUiPrefsRegionalLocale } from '@pages/settings/controllers/uiprefs/guards.ts';

class PreferenceControls {
    readonly #host: PreferencesManagerHost;
    readonly #synchronizers: Array<() => void> = [];
    readonly #disposers: Array<() => void> = [];

    constructor(host: PreferencesManagerHost) {
        this.#host = host;
    }

    setupEventListeners(): void {
        this.dispose();
        const currentLanguage = requireUiPrefsLanguage(this.#host.getUiPrefValue('language'));
        const currentClockFormat = requireUiPrefsClockFormat(this.#host.getUiPrefValue('clockFormat'));
        const currentRegionalLocale = requireUiPrefsRegionalLocale(this.#host.getUiPrefValue('regionalLocale'));
        const currentDateFormat = requireUiPrefsDateFormat(this.#host.getUiPrefValue('dateFormat'));
        const currentMeasurementUnits = requireUiPrefsMeasurementUnits(this.#host.getUiPrefValue('measurementUnits'));

        this.#bindSelect('language-select', 'Language select', 'language', (value) => value || currentLanguage);
        this.#bindSelect('clock-format-select', 'Clock format select', 'clockFormat', (value) => (value === '12h' || value === '24h' ? value : currentClockFormat));
        this.#bindSelect(UI_IDS.REGIONAL_LOCALE_SELECT, 'Regional locale select', 'regionalLocale', (value) => (isRegionalLocalePreference(value) ? value : currentRegionalLocale));
        this.#bindSelect(UI_IDS.DATE_FORMAT_SELECT, 'Date format select', 'dateFormat', (value) => (isDateFormatPreference(value) ? value : currentDateFormat));
        this.#bindSelect(UI_IDS.MEASUREMENT_UNITS_SELECT, 'Measurement units select', 'measurementUnits', (value) => (isMeasurementUnitsPreference(value) ? value : currentMeasurementUnits));
        this.#bindPreferenceSliders();
        this.#bindPreferenceToggles();
    }

    sync(): void {
        for (const synchronize of this.#synchronizers) synchronize();
        this.#syncClockSecondsToggle();
    }

    dispose(): void {
        this.#synchronizers.length = 0;
        const disposers = this.#disposers.splice(0);
        const failures: Error[] = [];
        for (const dispose of disposers) runCleanupStepCollectingFailure(dispose, failures);
        throwCollectedCleanupFailures(failures);
    }

    #bindSelect(id: string, label: string, key: UiPreferenceKey, normalize: (value: string) => string): void {
        const selectCandidate = this.#host.pageDom.optional(id);
        if (!selectCandidate) {
            return;
        }
        const select = narrowSelect(selectCandidate, label);
        this.#synchronizers.push(() => {
            const value = this.#host.getUiPrefValue(key);
            if (typeof value !== 'string') throw new TypeError(`uiPrefs.${key} must be a string`);
            if (select.value !== value) setSelectValueAndSyncDefault(select, value);
            if (id === 'language-select') syncFlagSelect(select);
        });
        if (id === 'language-select') syncFlagSelect(select);
        const dispose = this.#host.pageResources.on(select, 'change', (event: Event) => {
            const target = event.target;
            if (!(target instanceof HTMLSelectElement)) {
                return;
            }
            if (id === 'language-select') syncFlagSelect(target);
            this.#host.setUiPrefValue(key, normalize(target.value));
        });
        this.#disposers.push(dispose);
    }

    #bindPreferenceSliders(): void {
        for (const sliderDefinition of createPreferenceSliderDefinitions(this.#host)) {
            const sliderCandidate = this.#host.pageDom.optional(sliderDefinition.id);
            if (!sliderCandidate) {
                continue;
            }
            const slider = narrowInput(sliderCandidate, `Preference slider "${sliderDefinition.id}"`);
            const valueDisplay = this.#host.pageDom.optional(sliderDefinition.valueId);
            const synchronize = (): void => {
                const value = sliderDefinition.getValue();
                if (slider.value !== String(value)) slider.value = String(value);
                if (valueDisplay) this.#host.pageDom.updateText(valueDisplay, sliderDefinition.formatValue(value));
            };
            this.#synchronizers.push(synchronize);
            const dispose = this.#host.pageResources.on(slider, 'input', () => {
                const rawValue = readFiniteInputValueOrNull(slider);
                if (rawValue === null) {
                    return;
                }
                sliderDefinition.setValue(rawValue);
                synchronize();
            });
            this.#disposers.push(dispose);
        }
    }

    #bindPreferenceToggles(): void {
        for (const toggleConfig of createPreferenceToggleDefinitions(this.#host)) {
            const elementCandidate = this.#host.pageDom.optional(toggleConfig.id);
            if (!elementCandidate) {
                continue;
            }
            const element = narrowInput(elementCandidate, `Preference toggle "${toggleConfig.id}"`);
            this.#synchronizers.push(() => {
                const checked = toggleConfig.getValue();
                element.checked = checked;
                setControlDisabledState(element, toggleConfig.isDisabled());
                updateToggleLabel(element, { checked });
            });
            const disposeToggle = this.#host.pageResources.on(element, 'change', (event: Event) => {
                const target = event.target;
                if (!(target instanceof HTMLInputElement)) {
                    return;
                }

                const isEnabled = target.checked;
                toggleConfig.setValue(isEnabled);
                updateToggleLabel(element, { checked: isEnabled });
                this.#syncClockSecondsToggle();
            });
            this.#disposers.push(disposeToggle);
        }
        this.#syncClockSecondsToggle();
    }

    #syncClockSecondsToggle(): void {
        const secondsToggleCandidate = this.#host.pageDom.optional(UI_IDS.CLOCK_SECONDS_TOGGLE);
        if (!secondsToggleCandidate) {
            return;
        }
        const secondsToggle = narrowInput(secondsToggleCandidate, 'Clock seconds toggle');
        const headerClockEnabled = this.#host.getUiPrefValue('headerClockEnabled') !== false;
        const clockSecondsEnabled = headerClockEnabled && this.#host.getUiPrefValue('clockSecondsEnabled') === true;
        secondsToggle.checked = clockSecondsEnabled;
        setControlDisabledState(secondsToggle, !headerClockEnabled);
        updateToggleLabel(secondsToggle, { checked: clockSecondsEnabled });
        const secondsItem = requireClosestElement(secondsToggle, '.setting-item', 'Clock seconds toggle');
        if (!(secondsItem instanceof HTMLElement)) {
            throw new TypeError('Clock seconds setting item must be an HTMLElement');
        }
        setSettingItemApplicable(secondsItem, headerClockEnabled);
        this.#host.filterSettings();
    }
}

export { PreferenceControls };
