/* SoAI - Settings page load data mappers [frontend/assets/ts/pages/settings/controllers/page/loadDataMappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';

const createUiPrefsSnapshot = (page: SettingsRuntimeContext): JsonObject => {
    const storage = page.owners.storage;
    const languageService = page.owners.languageService;
    return {
        language: languageService.getLanguage(),
        promptEnhancerModel: storage.getPromptEnhancerModel(),
        clockFormat: storage.getClockFormat(),
        regionalLocale: storage.getRegionalLocale(),
        dateFormat: storage.getDateFormat(),
        measurementUnits: storage.getMeasurementUnits(),
        notificationDuration: storage.getNotificationDuration(),
        codeRecognitionEnabled: storage.getCodeRecognitionEnabled(),
        headerClockEnabled: storage.getHeaderClockEnabled(),
        clockSecondsEnabled: storage.getClockSecondsEnabled(),
        soundEffects: storage.getSoundEffects(),
        liveStatusOverlayEnabled: storage.getLiveStatusOverlayEnabled(),
        theme: storage.getTheme(),
        accentColor: storage.getAccentColor(),
        surfaceColor: storage.getSurfaceColor(),
        reduceMotions: storage.getReduceMotions(),
        glassEnabled: storage.getGlassEnabled(),
        pageAnimation: storage.getPageAnimation(),
        modalAnimation: storage.getModalAnimation(),
        notificationAnimation: storage.getNotificationAnimation(),
        animationSpeed: storage.getAnimationSpeed(),
        interfaceScale: storage.getInterfaceScale(),
        wallpaperOverlay: storage.getWallpaperOverlay(),
        solidBackground: storage.getSolidBackground(),
        headerAutoHide: storage.getHeaderAutoHide(),
        showScrollToTopButton: storage.getShowScrollToTopButton(),
        showMainStatusIndicator: storage.getShowMainStatusIndicator(),
        dashboardLocked: storage.getDashboardLocked(),
        chartColorMode: storage.getChartColorMode(),
        chartStaticColor: storage.getChartStaticColor()
    };
};

export { createUiPrefsSnapshot };
