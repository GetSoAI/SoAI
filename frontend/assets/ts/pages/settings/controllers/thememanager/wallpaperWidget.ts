/* SoAI - Settings page wallpaper widget [frontend/assets/ts/pages/settings/controllers/thememanager/wallpaperWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { createSettingsUiPreferenceFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSettingItem, renderSettingsSubgroup, renderSliderControl } from '@core/settings/settingsMarkup.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { renderColorClearButton } from '@pages/settings/controllers/thememanager/themeColorControlsWidget.ts';
import type { ThemeViewContext } from '@pages/settings/controllers/thememanager/contracts.ts';
import { requireUiPrefsSolidBackground } from '@pages/settings/controllers/uiprefs/guards.ts';

const renderSolidBackgroundSetting = (context: ThemeViewContext): string => {
    const clearLabel = i18n.t('settings.wallpaper.solidBackground.clear');
    const solidBackground = requireUiPrefsSolidBackground(context.host.getUiPrefValue('solidBackground'));
    return renderSettingItem({
        label: i18n.t('settings.wallpaper.solidBackground.label'),
        help: i18n.t('settings.wallpaper.solidBackground.help'),
        fieldKey: createSettingsUiPreferenceFieldKey('solidBackground'),
        attributes: { id: UI_IDS.SOLID_BACKGROUND_CONTAINER },
        control: `<div class="solid-background-controls"><input type="color" id="${UI_IDS.SOLID_BACKGROUND_PICKER}" class="setting-input setting-color-picker">${renderColorClearButton(UI_IDS.SOLID_BACKGROUND_CLEAR, clearLabel, solidBackground !== null)}</div>`
    });
};

const renderWallpaperSubgroup = (context: ThemeViewContext): string => {
    const uploadLabel = i18n.t('settings.wallpaper.upload.button');
    const downloadLabel = i18n.t('settings.wallpaper.downloadUrl.button');
    const wallpaperDetails = [
        renderSettingItem({
            label: i18n.t('settings.wallpaper.upload.label'),
            help: i18n.t('settings.wallpaper.upload.help'),
            className: 'wallpaper-upload-state',
            control: `<input type="file" id="${UI_IDS.WALLPAPER_FILE}" accept="image/*" class="u-hidden"><button type="button" id="${UI_IDS.WALLPAPER_UPLOAD}" class="ui-button ui-button--sm ui-variant-neutral" aria-label="${uploadLabel}" data-tooltip="${uploadLabel}">${uploadLabel}</button>`
        }),
        renderSettingItem({
            label: i18n.t('settings.wallpaper.downloadUrl.label'),
            help: i18n.t('settings.wallpaper.downloadUrl.help'),
            control: `<div class="url-input-group"><input type="url" id="${UI_IDS.WALLPAPER_URL}" class="setting-input" placeholder="${i18n.t('settings.wallpaper.downloadUrl.placeholder')}"><button type="button" id="${UI_IDS.WALLPAPER_DOWNLOAD}" class="ui-button ui-button--sm ui-variant-accent" aria-label="${downloadLabel}" data-tooltip="${downloadLabel}" hidden${renderControlDisabledAttributes(true)}>${downloadLabel}</button></div>`
        }),
        renderSettingItem({
            label: i18n.t('settings.wallpaper.overlay.label'),
            help: i18n.t('settings.wallpaper.overlay.help'),
            fieldKey: createSettingsUiPreferenceFieldKey('wallpaperOverlay'),
            control: renderSliderControl({ id: UI_IDS.WALLPAPER_OVERLAY_SLIDER, valueId: UI_IDS.WALLPAPER_OVERLAY_VALUE, min: 0, max: 100, step: 5, value: 0, valueLabel: '0%' })
        }),
        renderSettingItem({
            label: i18n.t('settings.wallpaper.info.label'),
            help: i18n.t('settings.wallpaper.info.help'),
            control: `<div id="${UI_IDS.WALLPAPER_INFO}" class="wallpaper-info-value">${i18n.t('settings.wallpaper.info.placeholder')}</div>`
        }),
        renderSolidBackgroundSetting(context)
    ].join('');

    return renderSettingsSubgroup({
        title: i18n.t('settings.wallpaper.subgroupTitle'),
        description: i18n.t('settings.wallpaper.subgroupDescription'),
        content: `<div class="wallpaper-layout"><div class="wallpaper-preview-column"><div class="wallpaper-preview-container"><div id="${UI_IDS.WALLPAPER_PREVIEW}" class="wallpaper-preview"></div><p id="${UI_IDS.NO_WALLPAPER_MESSAGE}" class="no-wallpaper-message">${i18n.t('settings.wallpaper.noWallpaperMessage')}</p></div></div><div class="wallpaper-details-column">${wallpaperDetails}</div></div>`
    });
};

const renderSolidBackgroundSubgroup = (context: ThemeViewContext): string =>
    renderSettingsSubgroup({
        title: i18n.t('settings.wallpaper.subgroupTitle'),
        description: i18n.t('settings.wallpaper.subgroupDescription'),
        content: `<div class="wallpaper-details-column">${renderSolidBackgroundSetting(context)}</div>`
    });

export { renderSolidBackgroundSubgroup, renderWallpaperSubgroup };
