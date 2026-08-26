/* SoAI - Settings page theme manager effects [frontend/assets/ts/pages/settings/controllers/thememanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireClosestElement } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { narrowButton, narrowInput, narrowSelect } from '@core/dom/narrowElement.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { i18n } from '@core/i18n/index.ts';
import { setSettingItemApplicable } from '@core/settings/settingItemApplicability.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import type { AddThemeManagerCleanup, ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';
import { formatWallpaperInfo } from '@pages/settings/controllers/thememanager/mappers.ts';

interface ThemePreferenceEffectsDependencies {
    host: ThemeManagerHost;
    addCleanup: AddThemeManagerCleanup;
    updatePreferenceToggleLabel: (element: Element, enabled?: boolean) => void;
}

interface WallpaperRefreshDependencies {
    host: ThemeManagerHost;
    isMounted: () => boolean;
    expectedToken: number;
    isTokenActive: (token: number) => boolean;
}

const bindSimpleToggleControls = (dependencies: ThemePreferenceEffectsDependencies): void => {
    const { host, addCleanup, updatePreferenceToggleLabel } = dependencies;
    const bindToggle = (options: { id: string; uiPrefKey: UiPreferenceKey }): void => {
        const element = narrowInput(host.pageDom.requireHTMLElement(options.id), `Toggle "${options.id}"`);
        const current = host.getUiPrefValue(options.uiPrefKey);
        if (typeof current !== 'boolean') {
            throw new TypeError(`uiPrefs.${options.uiPrefKey} must be a boolean`);
        }
        element.checked = current;
        updatePreferenceToggleLabel(element, current);

        addCleanup(
            host.pageResources.on(element, 'change', () => {
                host.setUiPrefValue(options.uiPrefKey, element.checked);
                updatePreferenceToggleLabel(element, element.checked);
            })
        );
    };

    bindToggle({ id: 'header-auto-hide-toggle', uiPrefKey: 'headerAutoHide' });
    bindToggle({ id: 'scroll-to-top-button-toggle', uiPrefKey: 'showScrollToTopButton' });
    bindToggle({ id: UI_IDS.CODE_RECOGNITION_TOGGLE, uiPrefKey: 'codeRecognitionEnabled' });
    bindToggle({ id: 'sidebar-status-indicator-toggle', uiPrefKey: 'showMainStatusIndicator' });
    bindToggle({ id: 'dashboard-lock-toggle', uiPrefKey: 'dashboardLocked' });
};

const setupChartsEventListeners = (dependencies: { host: ThemeManagerHost; addCleanup: AddThemeManagerCleanup }): void => {
    const { host, addCleanup } = dependencies;
    const modeSelect = narrowSelect(host.pageDom.requireHTMLElement('chart-color-mode-select'), 'Chart color mode select');
    const colorItem = host.pageDom.requireHTMLElement('chart-static-color-item');
    const colorPicker = narrowInput(host.pageDom.requireHTMLElement('chart-static-color-picker'), 'Chart static color picker');
    if (colorPicker.type !== 'color') {
        throw new TypeError('Chart static color picker must be type="color"');
    }

    const modeValue = host.getUiPrefValue('chartColorMode');
    if (typeof modeValue !== 'string' || !modeValue.trim()) {
        throw new TypeError('uiPrefs.chartColorMode must be a non-empty string');
    }
    setSelectValueAndSyncDefault(modeSelect, modeValue);
    setSettingItemApplicable(colorItem, modeSelect.value === 'static');

    const staticColorValue = host.getUiPrefValue('chartStaticColor');
    if (typeof staticColorValue !== 'string' || !staticColorValue.trim()) {
        throw new TypeError('uiPrefs.chartStaticColor must be a non-empty string');
    }
    colorPicker.value = staticColorValue;

    addCleanup(
        host.pageResources.on(modeSelect, 'change', () => {
            host.setUiPrefValue('chartColorMode', modeSelect.value);
            setSettingItemApplicable(colorItem, modeSelect.value === 'static');
        })
    );
    addCleanup(
        host.pageResources.on(colorPicker, 'change', () => {
            host.setUiPrefValue('chartStaticColor', colorPicker.value);
        })
    );
};

const refreshWallpaperPreview = async (dependencies: WallpaperRefreshDependencies): Promise<void> => {
    const { host, isMounted, expectedToken } = dependencies;
    const storage = host.storage;
    const previousUrl = host.getCurrentWallpaperUrl();
    const previousSolid = host.getCurrentSolidBackground();

    host.setCurrentSolidBackground(storage.getSolidBackground());
    const status = await host.getWallpaperStatus();
    if (!isMounted()) {
        return;
    }
    if (!dependencies.isTokenActive(expectedToken)) {
        return;
    }

    const url = status.url;
    const hasWallpaper = status.exists && url !== null;
    const metadata = hasWallpaper ? status.metadata : null;
    host.setCurrentWallpaperMetadata(metadata);
    host.setCurrentWallpaperUrl(hasWallpaper ? url : null);
    updateWallpaperUI(host, hasWallpaper, url);

    if (previousUrl !== host.getCurrentWallpaperUrl() || previousSolid !== host.getCurrentSolidBackground()) {
        host.scheduleWallpaperRefresh();
    }
};

const updateWallpaperUI = (host: ThemeManagerHost, hasWallpaper: boolean, url: string | null): void => {
    if (hasWallpaper && !url) {
        throw new Error('Wallpaper url is required when wallpaper exists');
    }

    const preview = host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_PREVIEW);
    preview.style.setProperty('background-image', hasWallpaper ? `url("${url}")` : 'none');
    dom.setVisibility(preview, hasWallpaper);

    const noWallpaperMessage = host.pageDom.requireHTMLElement(UI_IDS.NO_WALLPAPER_MESSAGE);
    dom.setVisibility(noWallpaperMessage, !hasWallpaper);
    updateWallpaperUploadControl(host, hasWallpaper);

    const overlaySlider = narrowInput(host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_OVERLAY_SLIDER), 'Wallpaper overlay slider');
    const overlayItem = requireClosestElement(overlaySlider, '.setting-item', 'Wallpaper overlay slider');
    if (!(overlayItem instanceof HTMLElement)) {
        throw new TypeError('Wallpaper overlay setting item must be an HTMLElement');
    }
    setSettingItemApplicable(overlayItem, hasWallpaper);

    const info = host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_INFO);
    const infoItem = requireClosestElement(info, '.setting-item', 'Wallpaper info');
    if (!(infoItem instanceof HTMLElement)) {
        throw new TypeError('Wallpaper info setting item must be an HTMLElement');
    }
    setSettingItemApplicable(infoItem, hasWallpaper);
    host.pageDom.updateText(info, hasWallpaper ? formatWallpaperInfo(host.getCurrentWallpaperMetadata()) : '');

    const solidBackgroundContainer = host.pageDom.requireHTMLElement(UI_IDS.SOLID_BACKGROUND_CONTAINER);
    setSettingItemApplicable(solidBackgroundContainer, !hasWallpaper);
};

const updateWallpaperUploadControl = (host: ThemeManagerHost, hasWallpaper: boolean): void => {
    const uploadButton = narrowButton(host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_UPLOAD), 'Wallpaper upload button');
    const uploadItem = requireClosestElement(uploadButton, '.setting-item', 'Wallpaper upload button');
    const label = host.pageDom.requireHTMLElement('.setting-label', uploadItem);
    const help = host.pageDom.requireHTMLElement('.setting-help', uploadItem);

    const labelText = hasWallpaper ? i18n.t('settings.wallpaper.remove.label') : i18n.t('settings.wallpaper.upload.label');
    const helpText = hasWallpaper ? i18n.t('settings.wallpaper.remove.help') : i18n.t('settings.wallpaper.upload.help');
    const buttonText = hasWallpaper ? i18n.t('settings.wallpaper.remove.button') : i18n.t('settings.wallpaper.upload.button');
    host.pageDom.updateText(label, labelText);
    host.pageDom.updateText(help, helpText);
    host.pageDom.updateText(uploadButton, buttonText);
    uploadButton.setAttribute('aria-label', buttonText);
    setTooltipText(uploadButton, buttonText);
    uploadButton.classList.toggle('ui-variant-danger', hasWallpaper);
    uploadButton.classList.toggle('ui-variant-neutral', !hasWallpaper);
    if (uploadButton.getAttribute('aria-busy') !== 'true') {
        setControlDisabledState(uploadButton, false);
    }
};

export { bindSimpleToggleControls, refreshWallpaperPreview, setupChartsEventListeners };
