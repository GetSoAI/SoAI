/* SoAI - Settings page preferences rendering [frontend/assets/ts/pages/settings/controllers/preferences/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { DateFormatPreference, MeasurementUnitsPreference, RegionalLocalePreference } from '@core/localization/public.ts';
import { createSettingsUiPreferenceFieldKey, type UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSection, renderSelectControl, renderSettingItem, renderSettingsGroup, renderSettingsSubgroup, renderSliderControl, renderToggleControl } from '@core/settings/settingsMarkup.ts';
import type { ToggleLabelState } from '@core/toggleSwitch.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { PreferenceSliderDefinition } from '@pages/settings/controllers/preferences/preferenceSlidersDomain.ts';

interface PreferencesSectionViewModel {
    identityContent: string;
    languageOptions: Array<{ value: string; label: string }>;
    currentLanguage: string;
    clockFormat: '12h' | '24h';
    regionalLocale: RegionalLocalePreference;
    dateFormat: DateFormatPreference;
    measurementUnits: MeasurementUnitsPreference;
    preferenceSliders: PreferenceSliderDefinition[];
    preferenceLabels: ToggleLabelState;
    preferenceToggles: Array<{ id: string; uiPrefKey: UiPreferenceKey; label: string; help: string; checked: boolean; disabled: boolean; itemClassName?: string | undefined }>;
}

const renderPreferencesSection = ({ identityContent, languageOptions, currentLanguage, clockFormat, regionalLocale, dateFormat, measurementUnits, preferenceSliders, preferenceLabels, preferenceToggles }: PreferencesSectionViewModel): string => {
    const items = [
        renderSettingItem({
            label: i18n.t('settings.preferences.language.label'),
            help: i18n.t('settings.preferences.language.help'),
            fieldKey: createSettingsUiPreferenceFieldKey('language'),
            control: renderSelectControl({
                id: 'language-select',
                options: languageOptions,
                selected: currentLanguage
            })
        }),
        renderSettingItem({
            label: i18n.t('settings.preferences.clockFormat.label'),
            help: i18n.t('settings.preferences.clockFormat.help'),
            fieldKey: createSettingsUiPreferenceFieldKey('clockFormat'),
            control: renderSelectControl({
                id: 'clock-format-select',
                options: [
                    { value: '12h', label: i18n.t('settings.preferences.clockFormat.12h') },
                    { value: '24h', label: i18n.t('settings.preferences.clockFormat.24h') }
                ],
                selected: clockFormat
            })
        }),
        renderSettingItem({
            label: i18n.t('settings.preferences.regionalLocale.label'),
            help: i18n.t('settings.preferences.regionalLocale.help'),
            fieldKey: createSettingsUiPreferenceFieldKey('regionalLocale'),
            control: renderSelectControl({
                id: UI_IDS.REGIONAL_LOCALE_SELECT,
                options: [
                    { value: 'auto', label: i18n.t('settings.preferences.regionalLocale.auto') },
                    { value: 'browser', label: i18n.t('settings.preferences.regionalLocale.browser') },
                    { value: 'en-US', label: i18n.t('settings.preferences.regionalLocale.enUS') },
                    { value: 'en-GB', label: i18n.t('settings.preferences.regionalLocale.enGB') },
                    { value: 'it-IT', label: i18n.t('settings.preferences.regionalLocale.itIT') }
                ],
                selected: regionalLocale
            })
        }),
        renderSettingItem({
            label: i18n.t('settings.preferences.dateFormat.label'),
            help: i18n.t('settings.preferences.dateFormat.help'),
            fieldKey: createSettingsUiPreferenceFieldKey('dateFormat'),
            control: renderSelectControl({
                id: UI_IDS.DATE_FORMAT_SELECT,
                options: [
                    { value: 'auto', label: i18n.t('settings.preferences.dateFormat.auto') },
                    { value: 'us', label: i18n.t('settings.preferences.dateFormat.us') },
                    { value: 'eu', label: i18n.t('settings.preferences.dateFormat.eu') },
                    { value: 'iso', label: i18n.t('settings.preferences.dateFormat.iso') }
                ],
                selected: dateFormat
            })
        }),
        renderSettingItem({
            label: i18n.t('settings.preferences.measurementUnits.label'),
            help: i18n.t('settings.preferences.measurementUnits.help'),
            fieldKey: createSettingsUiPreferenceFieldKey('measurementUnits'),
            control: renderSelectControl({
                id: UI_IDS.MEASUREMENT_UNITS_SELECT,
                options: [
                    { value: 'auto', label: i18n.t('settings.preferences.measurementUnits.auto') },
                    { value: 'metric', label: i18n.t('settings.preferences.measurementUnits.metric') },
                    { value: 'imperial', label: i18n.t('settings.preferences.measurementUnits.imperial') }
                ],
                selected: measurementUnits
            })
        })
    ];

    for (const slider of preferenceSliders) {
        const value = slider.getValue();
        items.push(
            renderSettingItem({
                label: slider.getLabel(),
                help: slider.getHelp(),
                fieldKey: createSettingsUiPreferenceFieldKey(slider.uiPrefKey),
                control: renderSliderControl({ id: slider.id, valueId: slider.valueId, min: slider.min, max: slider.max, step: slider.step, value, valueLabel: slider.formatValue(value) })
            })
        );
    }

    for (const toggleConfig of preferenceToggles) {
        items.push(
            renderSettingItem({
                label: toggleConfig.label,
                help: toggleConfig.help,
                ...(toggleConfig.itemClassName ? { className: toggleConfig.itemClassName } : {}),
                fieldKey: createSettingsUiPreferenceFieldKey(toggleConfig.uiPrefKey),
                control: renderToggleControl({
                    id: toggleConfig.id,
                    checked: toggleConfig.checked,
                    disabled: toggleConfig.disabled,
                    labels: preferenceLabels
                })
            })
        );
    }

    return renderSection({
        title: i18n.t('settings.preferences.sectionTitle'),
        description: i18n.t('settings.preferences.description'),
        className: 'settings-section--preferences',
        content: `${identityContent}${renderSettingsSubgroup({
            title: i18n.t('settings.preferences.subgroupTitle'),
            description: i18n.t('settings.preferences.subgroupDescription'),
            content: renderSettingsGroup(items)
        })}`
    });
};

export { renderPreferencesSection };
