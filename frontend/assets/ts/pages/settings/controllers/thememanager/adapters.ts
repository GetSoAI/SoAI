/* SoAI - Settings page control layer theme manager adapters [frontend/assets/ts/pages/settings/controllers/thememanager/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { createSettingsUiPreferenceFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSettingItem, renderSettingsGroup, renderSettingsSubgroup, renderToggleControl } from '@core/settings/settingsMarkup.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { CustomizationType, ThemeViewContext } from '@pages/settings/controllers/thememanager/contracts.ts';

const renderCustomizationSettingItem = (type: CustomizationType): string => {
    const config = (() => {
        if (type === 'sidebar') {
            return {
                label: i18n.t('settings.sidebar.customization.label'),
                help: i18n.t('settings.sidebar.customization.description'),
                containerId: UI_IDS.SIDEBAR_CHECKBOXES_CONTAINER,
                btnId: UI_IDS.SIDEBAR_EDIT_BTN,
                buttonLabel: i18n.t('settings.sidebar.customization.edit')
            };
        }
        return {
            label: i18n.t('settings.dashboard.customization.label'),
            help: i18n.t('settings.dashboard.customization.description'),
            containerId: UI_IDS.DASHBOARD_CHECKBOXES_CONTAINER,
            btnId: UI_IDS.DASHBOARD_EDIT_BTN,
            buttonLabel: i18n.t('settings.dashboard.customization.edit')
        };
    })();

    const control = [`<button type="button" id="${config.btnId}" class="ui-button ui-button--sm"`, `aria-label="${config.buttonLabel}" data-tooltip="${config.buttonLabel}">`, config.buttonLabel, '</button>'].join(' ');

    return renderSettingItem({
        label: config.label,
        help: `${config.help}<div id="${config.containerId}" class="sidebar-page-list sidebar-page-list--hidden"></div>`,
        control
    });
};

const renderSidebarSubgroup = (context: ThemeViewContext): string => {
    const { host, getPreferenceStateLabels } = context;
    return renderSettingsSubgroup({
        title: i18n.t('settings.sidebar.customization.sectionTitle'),
        description: i18n.t('settings.sidebar.customization.description'),
        content: renderSettingsGroup([
            renderCustomizationSettingItem('sidebar'),
            renderSettingItem({
                label: i18n.t('settings.sidebar.statusIndicator.label'),
                help: i18n.t('settings.sidebar.statusIndicator.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('showMainStatusIndicator'),
                control: renderToggleControl({
                    id: 'sidebar-status-indicator-toggle',
                    checked: host.storage.getShowMainStatusIndicator(),
                    labels: getPreferenceStateLabels()
                })
            })
        ])
    });
};

const renderDashboardSubgroup = (context: ThemeViewContext): string => {
    const { host, getPreferenceStateLabels } = context;
    return renderSettingsSubgroup({
        title: i18n.t('settings.dashboard.customization.sectionTitle'),
        description: i18n.t('settings.dashboard.customization.description'),
        content: renderSettingsGroup([
            renderCustomizationSettingItem('dashboard'),
            renderSettingItem({
                label: i18n.t('settings.dashboard.lockLayout.label'),
                help: i18n.t('settings.dashboard.lockLayout.help'),
                fieldKey: createSettingsUiPreferenceFieldKey('dashboardLocked'),
                control: renderToggleControl({
                    id: 'dashboard-lock-toggle',
                    checked: host.storage.getDashboardLocked(),
                    labels: getPreferenceStateLabels()
                })
            })
        ])
    });
};

const renderSecondaryThemeSubgroups = (context: ThemeViewContext): string[] => {
    return [renderSidebarSubgroup(context), renderDashboardSubgroup(context)];
};

export { renderSecondaryThemeSubgroups };
