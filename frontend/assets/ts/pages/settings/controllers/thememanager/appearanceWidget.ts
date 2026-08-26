/* SoAI - Settings page appearance widget [frontend/assets/ts/pages/settings/controllers/thememanager/appearanceWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { securityApi } from '@core/security/public.ts';
import { createSettingsUiPreferenceFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSelectControl, renderSettingItem, renderSettingsGroup, renderSettingsSubgroup, renderToggleControl } from '@core/settings/settingsMarkup.ts';
import { normalizeAccentColorPreference } from '@core/theme/accentColor.ts';
import { normalizeSurfaceColorPreference } from '@core/theme/surfaceColor.ts';
import { getPreferenceStateLabels, UI_IDS } from '@features/settings/public.ts';
import { renderColorClearButton } from '@pages/settings/controllers/thememanager/themeColorControlsWidget.ts';
import type { ThemeManagerHost, ThemeViewContext } from '@pages/settings/controllers/thememanager/contracts.ts';
import { requireUiPrefsNonEmptyString } from '@pages/settings/controllers/uiprefs/guards.ts';

const renderChartSettingsItems = (host: ThemeManagerHost): string[] => {
    const colorMode = requireUiPrefsNonEmptyString(host.getUiPrefValue('chartColorMode'), 'uiPrefs.chartColorMode');
    const staticColor = requireUiPrefsNonEmptyString(host.getUiPrefValue('chartStaticColor'), 'uiPrefs.chartStaticColor');

    return [
        renderSettingItem({
            label: i18n.t('settings.charts.colorMode.label'),
            help: i18n.t('settings.charts.colorMode.help'),
            fieldKey: createSettingsUiPreferenceFieldKey('chartColorMode'),
            control: renderSelectControl({
                id: 'chart-color-mode-select',
                options: [
                    { value: 'disabled', label: i18n.t('settings.charts.colorMode.disabled') },
                    { value: 'static', label: i18n.t('settings.charts.colorMode.static') },
                    { value: 'auto', label: i18n.t('settings.charts.colorMode.auto') }
                ],
                selected: colorMode
            })
        }),
        renderSettingItem({
            label: i18n.t('settings.charts.staticColor.label'),
            help: i18n.t('settings.charts.staticColor.help'),
            fieldKey: createSettingsUiPreferenceFieldKey('chartStaticColor'),
            attributes: { id: 'chart-static-color-item', hidden: colorMode !== 'static' },
            control: `<input type="color" id="chart-static-color-picker" class="setting-input setting-color-picker" value="${securityApi.escapeAttribute(staticColor)}">`
        })
    ];
};

const renderAppearanceSubgroup = (context: ThemeViewContext): string => {
    const { host } = context;
    const themeValue = host.getUiPrefValue('theme');
    if (typeof themeValue !== 'string' || !themeValue.trim()) {
        throw new TypeError('uiPrefs.theme must be a non-empty string');
    }
    const clearLabel = i18n.t('settings.wallpaper.solidBackground.clear');
    const accentColor = normalizeAccentColorPreference(host.getUiPrefValue('accentColor'));
    const surfaceColor = normalizeSurfaceColorPreference(host.getUiPrefValue('surfaceColor'));

    return renderSettingsSubgroup({
        title: i18n.t('settings.appearance.subgroupTitle'),
        description: i18n.t('settings.appearance.subgroupDescription'),
        content: renderSettingsGroup([
            renderSettingItem({
                label: i18n.t('settings.appearance.theme.label'),
                help: i18n.t('settings.appearance.theme.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('theme', 'theme-select'),
                control: renderSelectControl({
                    id: 'theme-select',
                    options: [
                        { value: 'auto', label: i18n.t('settings.appearance.theme.autoLabel') },
                        { value: 'dark', label: i18n.t('settings.appearance.theme.dark') },
                        { value: 'light', label: i18n.t('settings.appearance.theme.light') }
                    ],
                    selected: themeValue
                })
            }),
            ...renderChartSettingsItems(host),
            renderSettingItem({
                label: i18n.t('settings.appearance.accentColor.label'),
                help: i18n.t('settings.appearance.accentColor.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('accentColor'),
                control: `<div class="solid-background-controls"><input type="color" id="${UI_IDS.ACCENT_COLOR_PICKER}" class="setting-input setting-color-picker">${renderColorClearButton(UI_IDS.ACCENT_COLOR_CLEAR, clearLabel, accentColor !== null)}</div>`
            }),
            renderSettingItem({
                label: i18n.t('settings.appearance.surfaceColor.label'),
                help: i18n.t('settings.appearance.surfaceColor.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('surfaceColor'),
                control: `<div class="solid-background-controls"><input type="color" id="${UI_IDS.SURFACE_COLOR_PICKER}" class="setting-input setting-color-picker">${renderColorClearButton(UI_IDS.SURFACE_COLOR_CLEAR, clearLabel, surfaceColor !== null)}</div>`
            })
        ])
    });
};

const renderCodeBlocksSubgroup = (context: ThemeViewContext): string => {
    const enabled = context.host.getUiPrefValue('codeRecognitionEnabled');
    if (typeof enabled !== 'boolean') {
        throw new TypeError('uiPrefs.codeRecognitionEnabled must be a boolean');
    }
    return renderSettingsSubgroup({
        title: i18n.t('settings.codeBlocks.subgroupTitle'),
        description: i18n.t('settings.codeBlocks.subgroupDescription'),
        content: renderSettingsGroup([
            renderSettingItem({
                label: i18n.t('settings.codeBlocks.codeRecognition.label'),
                help: i18n.t('settings.codeBlocks.codeRecognition.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('codeRecognitionEnabled'),
                control: renderToggleControl({
                    id: UI_IDS.CODE_RECOGNITION_TOGGLE,
                    checked: enabled,
                    labels: getPreferenceStateLabels()
                })
            })
        ])
    });
};

export { renderAppearanceSubgroup, renderCodeBlocksSubgroup };
