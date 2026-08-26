/* SoAI - Settings page preferences manager [frontend/assets/ts/pages/settings/controllers/PreferencesManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { readFiniteInputValueOrNull } from '@core/dom/formValues.ts';
import { narrowInput, narrowSelect } from '@core/dom/narrowElement.ts';
import { isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/localization/public.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import { buildLanguageOptions } from '@pages/settings/controllers/preferences/service.ts';
import { createPreferenceSliderDefinitions, type PreferenceSliderDefinition } from '@pages/settings/controllers/preferences/preferenceSlidersDomain.ts';
import { createPreferenceToggleDefinitions, getPreferenceStateLabels, type PreferenceToggleDefinition } from '@pages/settings/controllers/preferences/toggles.ts';
import type { PreferencesManagerDependencies, PreferencesManagerHost } from '@pages/settings/controllers/preferences/types.ts';
import { renderPreferencesSection } from '@pages/settings/controllers/preferences/view.ts';
import { requireUiPrefsClockFormat, requireUiPrefsDateFormat, requireUiPrefsLanguage, requireUiPrefsMeasurementUnits, requireUiPrefsRegionalLocale } from '@pages/settings/controllers/uiprefs/guards.ts';

class PreferencesManager {
    readonly #host: PreferencesManagerHost;
    #disposers: Array<() => void> = [];

    constructor({ host }: PreferencesManagerDependencies) {
        if (!host) {
            throw new Error('PreferencesManager requires a host');
        }
        this.#host = host;
    }

    render(identityContent = ''): TrustedHtml {
        const languageService = this.#host.languageService;
        const currentLanguage = requireUiPrefsLanguage(this.#host.getUiPrefValue('language'));
        const languageCandidates = languageService.getAvailableLanguages();

        const clockFormatValue = requireUiPrefsClockFormat(this.#host.getUiPrefValue('clockFormat'));
        const regionalLocaleValue = requireUiPrefsRegionalLocale(this.#host.getUiPrefValue('regionalLocale'));
        const dateFormatValue = requireUiPrefsDateFormat(this.#host.getUiPrefValue('dateFormat'));
        const measurementUnitsValue = requireUiPrefsMeasurementUnits(this.#host.getUiPrefValue('measurementUnits'));

        return toTrustedUiHtml(
            renderPreferencesSection({
                identityContent,
                languageOptions: buildLanguageOptions(languageCandidates, currentLanguage),
                currentLanguage,
                clockFormat: clockFormatValue,
                regionalLocale: regionalLocaleValue,
                dateFormat: dateFormatValue,
                measurementUnits: measurementUnitsValue,
                preferenceSliders: this.#getPreferenceSliderDefinitions(),
                preferenceLabels: getPreferenceStateLabels(),
                preferenceToggles: this.#getPreferenceToggleDefinitions().map((toggle) => ({
                    id: toggle.id,
                    uiPrefKey: toggle.uiPrefKey,
                    label: toggle.getLabel(),
                    help: toggle.getHelp(),
                    checked: toggle.getValue(),
                    disabled: toggle.isDisabled(),
                    itemClassName: toggle.itemClassName
                }))
            })
        );
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

    #bindSelect(id: string, label: string, key: UiPreferenceKey, normalize: (value: string) => string): void {
        const selectCandidate = this.#host.pageDom.optional(id);
        if (!selectCandidate) {
            return;
        }
        const select = narrowSelect(selectCandidate, label);
        const dispose = this.#host.pageResources.on(select, 'change', (event: Event) => {
            const target = event.target;
            if (!(target instanceof HTMLSelectElement)) {
                return;
            }
            this.#host.setUiPrefValue(key, normalize(target.value));
        });
        this.#disposers.push(dispose);
    }

    #bindPreferenceSliders(): void {
        for (const sliderDefinition of this.#getPreferenceSliderDefinitions()) {
            const sliderCandidate = this.#host.pageDom.optional(sliderDefinition.id);
            if (!sliderCandidate) {
                continue;
            }
            const slider = narrowInput(sliderCandidate, `Preference slider "${sliderDefinition.id}"`);
            const valueDisplay = this.#host.pageDom.optional(sliderDefinition.valueId);
            const dispose = this.#host.pageResources.on(slider, 'input', () => {
                const rawValue = readFiniteInputValueOrNull(slider);
                if (rawValue === null) {
                    return;
                }
                sliderDefinition.setValue(rawValue);
                const normalizedValue = sliderDefinition.getValue();
                slider.value = String(normalizedValue);
                if (valueDisplay) {
                    this.#host.pageDom.updateText(valueDisplay, sliderDefinition.formatValue(normalizedValue));
                }
            });
            this.#disposers.push(dispose);
        }
    }

    #bindPreferenceToggles(): void {
        for (const toggleConfig of this.#getPreferenceToggleDefinitions()) {
            const elementCandidate = this.#host.pageDom.optional(toggleConfig.id);
            if (!elementCandidate) {
                continue;
            }
            const element = narrowInput(elementCandidate, `Preference toggle "${toggleConfig.id}"`);
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

    #getPreferenceToggleDefinitions(): PreferenceToggleDefinition[] {
        return createPreferenceToggleDefinitions(this.#host);
    }

    #getPreferenceSliderDefinitions(): PreferenceSliderDefinition[] {
        return createPreferenceSliderDefinitions(this.#host);
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
    }

    dispose(): void {
        for (const disposer of this.#disposers) {
            disposer();
        }
        this.#disposers = [];
    }
}

export { PreferencesManager };
