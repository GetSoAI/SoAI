/* SoAI - Settings page preferences manager [frontend/assets/ts/pages/settings/controllers/PreferencesManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { ConfigurationManager } from '@core/configurationManager.ts';
import { readOcrPreference, requireOcrLanguage, type OcrLanguage } from '@core/api/contracts/ocrLanguageContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import type { PreparedSaveUnit } from '@core/save/public.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { requireClosestElement } from '@core/dom/attributes.ts';
import { readFiniteInputValueOrNull } from '@core/dom/formValues.ts';
import { narrowInput, narrowSelect } from '@core/dom/narrowElement.ts';
import { isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/localization/public.ts';
import { setSettingItemApplicable } from '@core/settings/settingItemApplicability.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import { buildLanguageOptions } from '@pages/settings/controllers/preferences/service.ts';
import { createPreferenceSliderDefinitions, type PreferenceSliderDefinition } from '@pages/settings/controllers/preferences/preferenceSlidersDomain.ts';
import { createPreferenceToggleDefinitions, getPreferenceStateLabels, type PreferenceToggleDefinition } from '@pages/settings/controllers/preferences/toggles.ts';
import type { PreferencesManagerDependencies, PreferencesManagerHost } from '@pages/settings/controllers/preferences/types.ts';
import { renderOcrLanguageControl, renderPreferencesSection } from '@pages/settings/controllers/preferences/view.ts';
import { requireUiPrefsClockFormat, requireUiPrefsDateFormat, requireUiPrefsLanguage, requireUiPrefsMeasurementUnits, requireUiPrefsRegionalLocale } from '@pages/settings/controllers/uiprefs/guards.ts';

class PreferencesManager {
    readonly #host: PreferencesManagerHost;
    #disposers: Array<() => void> = [];
    readonly #ocrConfig: ConfigurationManager;
    readonly #ocrAbort = new AbortController();
    #ocrLanguages: readonly OcrLanguage[] = [];
    #ocrOwner: number | null = null;
    #ocrLoadSequence = 0;
    #ocrDraftSequence = 0;
    #ocrSaving = false;
    #ocrReady = false;
    #ocrResetDraftSequence: number | null = null;

    constructor({ host }: PreferencesManagerDependencies) {
        if (!host) {
            throw new Error('PreferencesManager requires a host');
        }
        this.#host = host;
        this.#ocrConfig = host.createConfigurationManager();
        this.#ocrConfig.initialize({ language: 'eng' });
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
                ocrOptions: this.#ocrOptions(),
                ocrLanguage: this.#ocrReady ? this.#ocrLanguage() : '',
                ocrReady: this.#ocrReady,
                ocrAvailable: this.#ocrReady && this.#ocrLanguages.some((entry) => entry.code === this.#ocrLanguage() && entry.available),
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
        this.#clearListeners();
        const ocrCandidate = this.#host.pageDom.optional('ocr-language-select');
        if (ocrCandidate && this.#ocrReady) {
            const select = narrowSelect(ocrCandidate, 'OCR language select');
            this.#disposers.push(
                this.#host.pageResources.on(select, 'change', () => {
                    const language = requireOcrLanguage(select.value, this.#ocrLanguages);
                    if (!this.#ocrLanguages.some((entry) => entry.code === language && entry.available)) return;
                    this.#ocrConfig.updateValue('language', language);
                    ++this.#ocrDraftSequence;
                    this.syncOcrDirtyState();
                    this.#syncOcrHelp(select);
                    this.#host.notifySaveChanged();
                })
            );
        }
        this.syncOcrDirtyState();
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
        const secondsItem = requireClosestElement(secondsToggle, '.setting-item', 'Clock seconds toggle');
        if (!(secondsItem instanceof HTMLElement)) {
            throw new TypeError('Clock seconds setting item must be an HTMLElement');
        }
        setSettingItemApplicable(secondsItem, headerClockEnabled);
        this.#host.filterSettings();
    }

    async loadOcrPreference(reset = false): Promise<void> {
        if (this.#ocrAbort.signal.aborted || this.#host.isDestroyed() || this.#ocrSaving || (!reset && this.hasOcrChanges() && this.#ocrResetDraftSequence === null)) return;
        if (reset) this.#ocrResetDraftSequence = this.#ocrDraftSequence;
        const sequence = ++this.#ocrLoadSequence;
        const draftSequence = this.#ocrResetDraftSequence ?? this.#ocrDraftSequence;
        const owner = this.#host.getCurrentUserId();
        if (owner === null) throw new Error('OCR settings require an authenticated user.');
        try {
            const [languages, preferences] = await Promise.all([this.#host.loadOcrLanguages(this.#ocrAbort.signal), this.#host.loadPreferences(this.#ocrAbort.signal)]);
            const language = readOcrPreference(preferences, languages);
            if (sequence !== this.#ocrLoadSequence || this.#ocrAbort.signal.aborted || this.#host.isDestroyed() || owner !== this.#host.getCurrentUserId() || this.#ocrSaving || (!reset && this.hasOcrChanges() && this.#ocrResetDraftSequence === null)) return;
            const newerDraft = this.#ocrResetDraftSequence !== null && draftSequence !== this.#ocrDraftSequence ? requireOcrLanguage(this.#ocrConfig.getValue('language'), languages) : null;
            this.#ocrLanguages = languages;
            this.#ocrOwner = owner;
            this.#ocrConfig.initialize({ language });
            if (newerDraft !== null) this.#ocrConfig.updateValue('language', newerDraft);
            this.#ocrReady = true;
            this.#ocrResetDraftSequence = null;
            this.syncOcrDirtyState();
        } catch (error) {
            const normalizedError = ensureError(error);
            if (isAbortError(normalizedError) || this.#ocrAbort.signal.aborted || sequence !== this.#ocrLoadSequence || owner !== this.#host.getCurrentUserId() || this.#host.isDestroyed() || this.#ocrSaving || (!reset && this.hasOcrChanges() && this.#ocrResetDraftSequence === null)) return;
            this.#ocrReady = false;
            this.#host.feedback.handle(normalizedError, 'OCR settings load');
        }
    }

    async refreshOcrPreference(): Promise<void> {
        const resetRefresh = this.#ocrResetDraftSequence !== null;
        if (this.#ocrSaving || (this.hasOcrChanges() && !resetRefresh)) return;
        await this.loadOcrPreference();
        if (this.#ocrAbort.signal.aborted || this.#host.isDestroyed() || this.#ocrSaving || (this.hasOcrChanges() && !resetRefresh)) return;
        const select = this.#host.pageDom.optional('ocr-language-select');
        if (!select) return;
        const control = requireClosestElement(select, '.setting-control', 'OCR language setting');
        if (!(control instanceof HTMLElement)) throw new TypeError('OCR setting control must be an HTMLElement.');
        this.#host.pageDom.updateHtml(control, toTrustedUiHtml(renderOcrLanguageControl(this.#ocrOptions(), this.#ocrReady ? this.#ocrLanguage() : '', this.#ocrReady)));
        const refreshed = this.#host.pageDom.requireHTMLElement('ocr-language-select');
        this.#syncOcrHelp(refreshed);
        this.setupEventListeners();
    }

    #syncOcrHelp(select: HTMLElement): void {
        const item = requireClosestElement(select, '.setting-item', 'OCR language setting');
        if (!(item instanceof HTMLElement)) throw new TypeError('OCR setting item must be an HTMLElement.');
        const help = this.#host.pageDom.optionalHTMLElement('.setting-help', item);
        if (help instanceof HTMLElement) {
            const available = this.#ocrReady && this.#ocrLanguages.some((entry) => entry.code === this.#ocrLanguage() && entry.available);
            this.#host.pageDom.updateText(help, available ? i18n.t('settings.preferences.ocrLanguage.help') : i18n.t('settings.preferences.ocrLanguage.unavailable'));
        }
    }

    hasOcrChanges(): boolean {
        return this.#ocrConfig.hasChanges;
    }

    syncOcrDirtyState(): void {
        this.#host.syncManualDirtyField('ocr-language', this.hasOcrChanges(), !this.hasOcrChanges() || this.#ocrReady);
    }

    prepareOcrSave(): PreparedSaveUnit {
        const language = this.#ocrLanguage();
        const owner = this.#ocrOwner;
        const valid = (): boolean => this.#ocrReady && owner !== null && owner === this.#host.getCurrentUserId() && !this.#host.isDestroyed() && !this.#ocrAbort.signal.aborted;
        return {
            isValid: valid,
            save: async () => {
                if (!valid() || owner === null) return { type: 'stop' };
                this.#ocrSaving = true;
                ++this.#ocrLoadSequence;
                try {
                    const response = await this.#host.saveOcrPreference(language, owner, this.#ocrAbort.signal);
                    if (!valid()) return { type: 'stop' };
                    if (readOcrPreference(response, this.#ocrLanguages) !== language) throw new Error('OCR preference acknowledgement differs from the request.');
                    const currentLanguage = this.#ocrLanguage();
                    this.#ocrConfig.applyCommittedPatch({ language });
                    if (currentLanguage !== language) this.#ocrConfig.updateValue('language', currentLanguage);
                    return;
                } finally {
                    this.#ocrSaving = false;
                    if (valid()) {
                        this.syncOcrDirtyState();
                        this.#host.notifySaveChanged();
                    }
                }
            }
        };
    }

    #ocrLanguage(): string {
        return requireOcrLanguage(this.#ocrConfig.getValue('language'), this.#ocrLanguages);
    }

    #ocrOptions(): Array<{ value: string; label: string; disabled: boolean }> {
        if (!this.#ocrReady) return [];
        const uiLanguages = this.#host.languageService.getAvailableLanguages();
        const candidates = this.#ocrLanguages.map((entry) => {
            const uiLanguage = uiLanguages.find((candidate) => candidate.code === entry.uiLocale);
            return { code: entry.code, name: uiLanguage?.name ?? entry.nativeName, flag: uiLanguage?.flag ?? entry.flag, direction: uiLanguage?.direction ?? 'ltr', region: uiLanguage?.region ?? null };
        });
        return buildLanguageOptions(candidates, this.#ocrLanguage()).map((option) => ({ ...option, disabled: !this.#ocrLanguages.some((entry) => entry.code === option.value && entry.available) }));
    }

    dispose(): void {
        this.#ocrAbort.abort();
        ++this.#ocrLoadSequence;
        this.#clearListeners();
    }

    #clearListeners(): void {
        for (const disposer of this.#disposers) {
            disposer();
        }
        this.#disposers = [];
    }
}

export { PreferencesManager };
