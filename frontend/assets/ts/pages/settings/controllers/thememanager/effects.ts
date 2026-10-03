/* SoAI - Settings page theme manager effects [frontend/assets/ts/pages/settings/controllers/thememanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireClosestElement, requireNonNegativeIntegerDataAttribute } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { narrowButton, narrowInput, narrowSelect } from '@core/dom/narrowElement.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { setSettingItemApplicable } from '@core/settings/settingItemApplicability.ts';
import { isDefaultWallpaperId, resolveDefaultWallpaperUrl, type DefaultWallpaperId } from '@core/theme/defaultWallpapers.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import type { AddThemeManagerCleanup, ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';
import { formatWallpaperInfo } from '@pages/settings/controllers/thememanager/mappers.ts';
import { resolveWallpaperView, WALLPAPER_REMOVE_VARIANT_CLASS, WALLPAPER_UPLOAD_VARIANT_CLASS, type WallpaperUploadControlView } from '@pages/settings/controllers/thememanager/wallpaperPresenceState.ts';

interface ThemePreferenceEffectsDependencies {
    host: ThemeManagerHost;
    addCleanup: AddThemeManagerCleanup;
    updatePreferenceToggleLabel: (element: Element, enabled?: boolean) => void;
}

interface WallpaperRefreshDependencies {
    host: ThemeManagerHost;
    isMounted: () => boolean;
    signal: AbortSignal;
    isCurrent: () => boolean;
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
            host.filterSettings();
        })
    );
    addCleanup(
        host.pageResources.on(colorPicker, 'change', () => {
            host.setUiPrefValue('chartStaticColor', colorPicker.value);
        })
    );
};

const refreshWallpaperPreview = async (dependencies: WallpaperRefreshDependencies): Promise<void> => {
    const { host, isMounted } = dependencies;
    const storage = host.storage;
    const previousUrl = host.getCurrentWallpaper()?.url ?? null;
    const previousSolid = host.getCurrentSolidBackground();

    host.setCurrentSolidBackground(storage.getSolidBackground());
    const status = await host.getWallpaperStatus(dependencies.signal);
    if (!isMounted()) {
        return;
    }
    if (!dependencies.isCurrent()) {
        return;
    }

    const url = status.url;
    host.setCurrentWallpaper(status.exists && url !== null ? { url, metadata: status.metadata } : null);
    updateWallpaperUI(host);

    if (previousUrl !== (host.getCurrentWallpaper()?.url ?? null) || previousSolid !== host.getCurrentSolidBackground()) {
        host.scheduleWallpaperRefresh();
    }
};

const requireSettingItem = (host: ThemeManagerHost, elementId: string, context: string): HTMLElement => {
    const item = requireClosestElement(host.pageDom.requireHTMLElement(elementId), '.setting-item', context);
    if (!(item instanceof HTMLElement)) {
        throw new TypeError(`${context} setting item must be an HTMLElement`);
    }
    return item;
};

const resolvePreviewUrl = (host: ThemeManagerHost, defaultWallpaper: DefaultWallpaperId | null): string | null => {
    const wallpaper = host.getCurrentWallpaper();
    if (host.getWallpaperPresence() === 'present') {
        if (wallpaper === null) {
            throw new Error('Wallpaper url is required when wallpaper exists');
        }
        return wallpaper.url;
    }
    return defaultWallpaper === null ? null : resolveDefaultWallpaperUrl(defaultWallpaper);
};

const readBuiltInWallpaperOptionId = (option: Element): DefaultWallpaperId | null => {
    if (!option.hasAttribute('data-default-wallpaper-id')) {
        return null;
    }
    const id = requireNonNegativeIntegerDataAttribute(option, 'defaultWallpaperId', 'Built-in wallpaper option');
    if (!isDefaultWallpaperId(id)) {
        throw new RangeError(`Unknown built-in wallpaper ${id}`);
    }
    return id;
};

const syncBuiltInWallpaperSelection = (host: ThemeManagerHost, defaultWallpaper: DefaultWallpaperId | null): void => {
    const options = dom.resolveAll('.wallpaper-builtin-option', host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_BUILTIN_OPTIONS));
    for (const option of options) {
        option.setAttribute('aria-pressed', readBuiltInWallpaperOptionId(option) === defaultWallpaper ? 'true' : 'false');
    }
};

const updateWallpaperUI = (host: ThemeManagerHost): void => {
    const defaultWallpaper = host.storage.getDefaultWallpaper();
    const view = resolveWallpaperView(host.getWallpaperPresence(), defaultWallpaper !== null);
    const wallpaper = host.getCurrentWallpaper();
    const previewUrl = view.previewVisible ? resolvePreviewUrl(host, defaultWallpaper) : null;

    const preview = host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_PREVIEW);
    preview.style.setProperty('background-image', previewUrl !== null ? `url("${previewUrl}")` : 'none');
    dom.setVisibility(preview, view.previewVisible);
    dom.setVisibility(host.pageDom.requireHTMLElement(UI_IDS.NO_WALLPAPER_MESSAGE), view.messageVisible);
    updateWallpaperUploadControl(host, view.upload);

    setSettingItemApplicable(requireSettingItem(host, UI_IDS.WALLPAPER_BUILTIN_OPTIONS, 'Built-in wallpaper options'), view.builtInApplicable);
    syncBuiltInWallpaperSelection(host, defaultWallpaper);
    setSettingItemApplicable(requireSettingItem(host, UI_IDS.WALLPAPER_OVERLAY_SLIDER, 'Wallpaper overlay slider'), view.overlayApplicable);
    setSettingItemApplicable(requireSettingItem(host, UI_IDS.WALLPAPER_INFO, 'Wallpaper info'), view.detailsApplicable);
    host.pageDom.updateText(host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_INFO), view.detailsApplicable ? formatWallpaperInfo(wallpaper?.metadata ?? null) : '');
    setSettingItemApplicable(host.pageDom.requireHTMLElement(UI_IDS.SOLID_BACKGROUND_CONTAINER), view.solidApplicable);
    host.filterSettings();
};

const updateWallpaperUploadControl = (host: ThemeManagerHost, upload: WallpaperUploadControlView): void => {
    const uploadButton = narrowButton(host.pageDom.requireHTMLElement(UI_IDS.WALLPAPER_UPLOAD), 'Wallpaper upload button');
    const uploadItem = requireClosestElement(uploadButton, '.setting-item', 'Wallpaper upload button');
    host.pageDom.updateText(host.pageDom.requireHTMLElement('.setting-label', uploadItem), upload.label);
    host.pageDom.updateText(host.pageDom.requireHTMLElement('.setting-help', uploadItem), upload.help);
    host.pageDom.updateText(uploadButton, upload.buttonText);
    uploadButton.setAttribute('aria-label', upload.buttonText);
    setTooltipText(uploadButton, upload.buttonText);
    uploadButton.classList.toggle(WALLPAPER_REMOVE_VARIANT_CLASS, upload.removes);
    uploadButton.classList.toggle(WALLPAPER_UPLOAD_VARIANT_CLASS, !upload.removes);
    if (uploadButton.getAttribute('aria-busy') !== 'true') {
        setControlDisabledState(uploadButton, false);
    }
};

export { bindSimpleToggleControls, readBuiltInWallpaperOptionId, refreshWallpaperPreview, setupChartsEventListeners, updateWallpaperUI };
