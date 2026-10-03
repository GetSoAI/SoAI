/* SoAI - Settings page wallpaper widget [frontend/assets/ts/pages/settings/controllers/thememanager/wallpaperWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { i18n } from '@core/i18n/index.ts';
import { securityApi } from '@core/security/public.ts';
import { createSettingsUiPreferenceFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSettingItem, renderSettingsSubgroup, renderSliderControl } from '@core/settings/settingsMarkup.ts';
import { DEFAULT_WALLPAPER_IDS, resolveDefaultWallpaperThumbnailUrl, type DefaultWallpaperId } from '@core/theme/defaultWallpapers.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';
import { createOverflowNavButtonMarkup } from '@core/ui/controls/OverflowNav.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { renderColorClearButton } from '@pages/settings/controllers/thememanager/themeColorControlsWidget.ts';
import type { ThemeViewContext } from '@pages/settings/controllers/thememanager/contracts.ts';
import { formatWallpaperOverlayValue } from '@pages/settings/controllers/thememanager/mappers.ts';
import { resolveWallpaperUploadVariantClass, resolveWallpaperView } from '@pages/settings/controllers/thememanager/wallpaperPresenceState.ts';
import { requireUiPrefsWallpaperOverlay } from '@pages/settings/controllers/uiprefs/guards.ts';

const renderPresenceVisibilityAttributes = (visible: boolean): string => (visible ? ' aria-hidden="false"' : ' aria-hidden="true"');

const renderPresenceVisibilityClass = (visible: boolean): string => (visible ? '' : ` ${CSS_CLASSES.HIDDEN}`);

const renderSolidBackgroundSetting = (context: ThemeViewContext, applicable: boolean): string => {
    const clearLabel = i18n.t('settings.wallpaper.solidBackground.clear');
    const solidBackground = context.host.storage.getSolidBackground();
    return renderSettingItem({
        label: i18n.t('settings.wallpaper.solidBackground.label'),
        help: i18n.t('settings.wallpaper.solidBackground.help'),
        attributes: { id: UI_IDS.SOLID_BACKGROUND_CONTAINER, hidden: !applicable },
        control: `<div class="solid-background-controls"><input type="color" id="${UI_IDS.SOLID_BACKGROUND_PICKER}" class="setting-input setting-color-picker">${renderColorClearButton(UI_IDS.SOLID_BACKGROUND_CLEAR, clearLabel, solidBackground !== null)}</div>`
    });
};

const renderBuiltInWallpaperNavButton = (direction: 'left' | 'right'): string =>
    createOverflowNavButtonMarkup({
        direction,
        className: `wallpaper-builtin-nav wallpaper-builtin-nav--${direction} ui-icon-button`,
        iconName: direction === 'left' ? 'chevron-left' : 'chevron-right',
        iconOptions: { size: 20, strokeWidth: 1.5 }
    });

const renderBuiltInWallpaperOptionButton = (label: string, selected: boolean, attributes: string, content: string, isBusy: boolean): string => {
    const safeLabel = securityApi.escapeAttribute(label);
    const busyClass = isBusy ? ` ${CSS_CLASSES.BUSY_CONTROL}` : '';
    const busyAttribute = isBusy ? ' aria-busy="true"' : '';
    return `<button type="button" class="wallpaper-builtin-option${busyClass}"${attributes}${busyAttribute} aria-pressed="${selected ? 'true' : 'false'}" aria-label="${safeLabel}" data-tooltip="${safeLabel}">${content}</button>`;
};

const renderBuiltInWallpaperOption = (id: DefaultWallpaperId, selected: boolean): string => renderBuiltInWallpaperOptionButton(i18n.t('settings.wallpaper.builtIn.option', { number: id }), selected, ` data-default-wallpaper-id="${id}" data-busy-spinner="overlay"`, `<img src="${securityApi.escapeAttribute(resolveDefaultWallpaperThumbnailUrl(id))}" alt="" loading="lazy" decoding="async">`, true);

const renderNoBuiltInWallpaperOption = (selected: boolean): string => renderBuiltInWallpaperOptionButton(i18n.t('settings.wallpaper.builtIn.none'), selected, '', `${renderIconSlot(getIconSync('close', { size: 18, strokeWidth: 1.5, attributes: { 'aria-hidden': 'true', focusable: 'false' } }))}`, false);

const renderBuiltInWallpaperSetting = (context: ThemeViewContext, applicable: boolean): string => {
    const label = i18n.t('settings.wallpaper.builtIn.label');
    const selected = context.host.storage.getDefaultWallpaper();
    const options = renderNoBuiltInWallpaperOption(selected === null) + DEFAULT_WALLPAPER_IDS.map((id) => renderBuiltInWallpaperOption(id, id === selected)).join('');
    return renderSettingItem({
        label,
        help: i18n.t('settings.wallpaper.builtIn.help'),
        className: 'wallpaper-builtin-state',
        attributes: { hidden: !applicable },
        control: `<div class="wallpaper-builtin-carousel">${renderBuiltInWallpaperNavButton('left')}<div id="${UI_IDS.WALLPAPER_BUILTIN_OPTIONS}" class="wallpaper-builtin-options" role="group" aria-label="${securityApi.escapeAttribute(label)}">${options}</div>${renderBuiltInWallpaperNavButton('right')}</div>`
    });
};

const renderWallpaperSubgroup = (context: ThemeViewContext): string => {
    const view = resolveWallpaperView(context.wallpaperPresence, context.host.storage.getDefaultWallpaper() !== null);
    const upload = view.upload;
    const downloadLabel = i18n.t('settings.wallpaper.downloadUrl.button');
    const overlay = requireUiPrefsWallpaperOverlay(context.host.getUiPrefValue('wallpaperOverlay'));
    const wallpaperDetails = [
        renderBuiltInWallpaperSetting(context, view.builtInApplicable),
        renderSettingItem({
            label: upload.label,
            help: upload.help,
            className: 'wallpaper-upload-state',
            control: `<input type="file" id="${UI_IDS.WALLPAPER_FILE}" accept="image/*" class="u-hidden"><button type="button" id="${UI_IDS.WALLPAPER_UPLOAD}" class="ui-button ui-button--sm ${resolveWallpaperUploadVariantClass(upload)}" aria-label="${upload.buttonText}" data-tooltip="${upload.buttonText}">${upload.buttonText}</button>`
        }),
        renderSettingItem({
            label: i18n.t('settings.wallpaper.downloadUrl.label'),
            help: i18n.t('settings.wallpaper.downloadUrl.help'),
            control: `<div class="url-input-group"><input dir="ltr" type="url" id="${UI_IDS.WALLPAPER_URL}" class="setting-input" placeholder="${i18n.t('settings.wallpaper.downloadUrl.placeholder')}"><button type="button" id="${UI_IDS.WALLPAPER_DOWNLOAD}" class="ui-button ui-button--sm ui-variant-accent" aria-label="${downloadLabel}" data-tooltip="${downloadLabel}" hidden${renderControlDisabledAttributes(true)}>${downloadLabel}</button></div>`
        }),
        renderSettingItem({
            label: i18n.t('settings.wallpaper.overlay.label'),
            help: i18n.t('settings.wallpaper.overlay.help'),
            fieldKey: createSettingsUiPreferenceFieldKey('wallpaperOverlay'),
            attributes: { hidden: !view.overlayApplicable },
            control: renderSliderControl({ id: UI_IDS.WALLPAPER_OVERLAY_SLIDER, valueId: UI_IDS.WALLPAPER_OVERLAY_VALUE, min: 0, max: 100, step: 5, value: overlay, valueLabel: formatWallpaperOverlayValue(overlay) })
        }),
        renderSettingItem({
            label: i18n.t('settings.wallpaper.info.label'),
            help: i18n.t('settings.wallpaper.info.help'),
            attributes: { hidden: !view.detailsApplicable },
            control: `<div id="${UI_IDS.WALLPAPER_INFO}" class="wallpaper-info-value">${i18n.t('settings.wallpaper.info.placeholder')}</div>`
        }),
        renderSolidBackgroundSetting(context, view.solidApplicable)
    ].join('');

    return renderSettingsSubgroup({
        title: i18n.t('settings.wallpaper.subgroupTitle'),
        description: i18n.t('settings.wallpaper.subgroupDescription'),
        content: `<div class="wallpaper-layout"><div class="wallpaper-preview-column"><div class="wallpaper-preview-container"><div id="${UI_IDS.WALLPAPER_PREVIEW}" class="wallpaper-preview${renderPresenceVisibilityClass(view.previewVisible)}"${renderPresenceVisibilityAttributes(view.previewVisible)}></div><p id="${UI_IDS.NO_WALLPAPER_MESSAGE}" class="no-wallpaper-message${renderPresenceVisibilityClass(view.messageVisible)}"${renderPresenceVisibilityAttributes(view.messageVisible)}>${i18n.t('settings.wallpaper.noWallpaperMessage')}</p></div></div><div class="wallpaper-details-column">${wallpaperDetails}</div></div>`
    });
};

const renderSolidBackgroundSubgroup = (context: ThemeViewContext): string =>
    renderSettingsSubgroup({
        title: i18n.t('settings.wallpaper.subgroupTitle'),
        description: i18n.t('settings.wallpaper.subgroupDescription'),
        content: `<div class="wallpaper-details-column">${renderSolidBackgroundSetting(context, true)}</div>`
    });

export { renderSolidBackgroundSubgroup, renderWallpaperSubgroup };
