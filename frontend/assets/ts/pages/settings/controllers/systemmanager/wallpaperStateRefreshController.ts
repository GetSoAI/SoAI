/* SoAI - Settings page wallpaper state refresh controller [frontend/assets/ts/pages/settings/controllers/systemmanager/wallpaperStateRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton, narrowInput } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { ResetActionExecutionContext } from '@pages/settings/controllers/systemmanager/contracts.ts';
import { ThemeColorPreferenceController } from '@pages/settings/controllers/thememanager/ThemeColorPreferenceController.ts';
import { SOLID_BACKGROUND_PICKER_FALLBACK } from '@pages/settings/controllers/thememanager/themeColorControlsWidget.ts';

const refreshWallpaperFromState = (host: ResetActionExecutionContext['host']): void => {
    host.workflow.applyWallpaperOverlay(String(host.api.getWallpaperOverlay()));

    const overlaySlider = host.view.pageDom.optionalHTMLElement(UI_IDS.WALLPAPER_OVERLAY_SLIDER);
    if (overlaySlider) {
        host.view.setUIValue(narrowInput(overlaySlider, 'Wallpaper overlay slider'), String(host.api.getWallpaperOverlay()), {
            attribute: 'value'
        });
    }

    const overlayValueElement = host.view.pageDom.optionalHTMLElement(UI_IDS.WALLPAPER_OVERLAY_VALUE);
    if (overlayValueElement) {
        host.view.pageDom.updateText(overlayValueElement, i18n.t('settings.wallpaper.overlay.value', { percent: host.api.getWallpaperOverlay() }));
    }

    const solidPicker = host.view.pageDom.optionalHTMLElement(UI_IDS.SOLID_BACKGROUND_PICKER);
    if (solidPicker) {
        host.view.setUIValue(narrowInput(solidPicker, 'Solid background picker'), host.api.getSolidBackground() ?? SOLID_BACKGROUND_PICKER_FALLBACK, {
            attribute: 'value'
        });
    }

    const solidClearButton = host.view.pageDom.optionalHTMLElement(UI_IDS.SOLID_BACKGROUND_CLEAR);
    if (solidClearButton) {
        ThemeColorPreferenceController.setClearButtonVisibility(narrowButton(solidClearButton, 'Solid background clear button'), host.api.getSolidBackground() !== null);
    }

    host.workflow.refreshWallpaperPreview();
};

export { refreshWallpaperFromState };
