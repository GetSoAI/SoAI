/* SoAI - Settings page UI preferences [frontend/assets/ts/pages/settings/controllers/page/uiPreferences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isHexColorString } from '@core/theme/hexColor.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { requireUiPrefsAnimation, requireUiPrefsAnimationSpeed, requireUiPrefsBoolean, requireUiPrefsChartColorMode, requireUiPrefsClockFormat, requireUiPrefsDateFormat, requireUiPrefsInterfaceScale, requireUiPrefsLanguage, requireUiPrefsMeasurementUnits, requireUiPrefsNonEmptyString, requireUiPrefsNotificationDuration, requireUiPrefsNullableString, requireUiPrefsRegionalLocale, requireUiPrefsSolidBackground, requireUiPrefsTheme, requireUiPrefsWallpaperOverlay } from '@pages/settings/controllers/uiprefs/guards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

function requireHexColor(value: JsonValue | null | undefined, label: string, nullable: true): string | null;
function requireHexColor(value: JsonValue | null | undefined, label: string, nullable: false): string;
function requireHexColor(value: JsonValue | null | undefined, label: string, nullable: boolean): string | null {
    const color = nullable ? requireUiPrefsNullableString(value, label) : requireUiPrefsNonEmptyString(value, label);
    if (color !== null && !isHexColorString(color)) throw new TypeError(`${label} must be a hex color like #RRGGBB`);
    return color;
}

const readUiPreferencesForCommit = (current: Record<string, JsonValue | null | undefined>) => ({
    language: requireUiPrefsLanguage(current['language']),
    promptEnhancerModel: requireUiPrefsNullableString(current['promptEnhancerModel'], 'uiPrefs.promptEnhancerModel'),
    clockFormat: requireUiPrefsClockFormat(current['clockFormat']),
    regionalLocale: requireUiPrefsRegionalLocale(current['regionalLocale']),
    dateFormat: requireUiPrefsDateFormat(current['dateFormat']),
    measurementUnits: requireUiPrefsMeasurementUnits(current['measurementUnits']),
    notificationDuration: requireUiPrefsNotificationDuration(current['notificationDuration']),
    codeRecognitionEnabled: requireUiPrefsBoolean(current['codeRecognitionEnabled'], 'uiPrefs.codeRecognitionEnabled'),
    headerClockEnabled: requireUiPrefsBoolean(current['headerClockEnabled'], 'uiPrefs.headerClockEnabled'),
    clockSecondsEnabled: requireUiPrefsBoolean(current['clockSecondsEnabled'], 'uiPrefs.clockSecondsEnabled'),
    soundEffects: requireUiPrefsBoolean(current['soundEffects'], 'uiPrefs.soundEffects'),
    liveStatusOverlayEnabled: requireUiPrefsBoolean(current['liveStatusOverlayEnabled'], 'uiPrefs.liveStatusOverlayEnabled'),
    theme: requireUiPrefsTheme(current['theme']),
    accentColor: requireHexColor(current['accentColor'], 'uiPrefs.accentColor', true),
    surfaceColor: requireHexColor(current['surfaceColor'], 'uiPrefs.surfaceColor', true),
    reduceMotions: requireUiPrefsBoolean(current['reduceMotions'], 'uiPrefs.reduceMotions'),
    glassEnabled: requireUiPrefsBoolean(current['glassEnabled'], 'uiPrefs.glassEnabled'),
    pageAnimation: requireUiPrefsAnimation(current['pageAnimation'], 'uiPrefs.pageAnimation'),
    modalAnimation: requireUiPrefsAnimation(current['modalAnimation'], 'uiPrefs.modalAnimation'),
    notificationAnimation: requireUiPrefsAnimation(current['notificationAnimation'], 'uiPrefs.notificationAnimation'),
    animationSpeed: requireUiPrefsAnimationSpeed(current['animationSpeed']),
    interfaceScale: requireUiPrefsInterfaceScale(current['interfaceScale']),
    wallpaperOverlay: requireUiPrefsWallpaperOverlay(current['wallpaperOverlay']),
    solidBackground: requireUiPrefsSolidBackground(current['solidBackground']),
    headerAutoHide: requireUiPrefsBoolean(current['headerAutoHide'], 'uiPrefs.headerAutoHide'),
    showScrollToTopButton: requireUiPrefsBoolean(current['showScrollToTopButton'], 'uiPrefs.showScrollToTopButton'),
    showMainStatusIndicator: requireUiPrefsBoolean(current['showMainStatusIndicator'], 'uiPrefs.showMainStatusIndicator'),
    dashboardLocked: requireUiPrefsBoolean(current['dashboardLocked'], 'uiPrefs.dashboardLocked'),
    defaultPage: requireUiPrefsNullableString(current['defaultPage'], 'uiPrefs.defaultPage'),
    chartColorMode: requireUiPrefsChartColorMode(current['chartColorMode']),
    chartStaticColor: requireHexColor(current['chartStaticColor'], 'uiPrefs.chartStaticColor', false)
});

const commitUiPreferences = async (page: SettingsRuntimeContext, state: SettingsPageState): Promise<boolean> => {
    const manager = state.uiPrefsManager;
    if (!manager || !manager.hasChanges) {
        return false;
    }

    const current = manager.currentData;
    const preferences = readUiPreferencesForCommit(current);
    const solidBackgroundChanged = current['solidBackground'] !== manager.originalData['solidBackground'];
    const storage = page.owners.storage;

    const language = preferences.language;
    if (language !== page.owners.languageService.getLanguage()) {
        await page.owners.languageService.setLanguage(language);
    }

    const promptEnhancerModel = preferences.promptEnhancerModel;
    storage.setPromptEnhancerModel(promptEnhancerModel ?? null);

    const clockFormat = preferences.clockFormat;
    storage.setClockFormat(clockFormat);

    const regionalLocale = preferences.regionalLocale;
    storage.setRegionalLocale(regionalLocale);

    const dateFormat = preferences.dateFormat;
    storage.setDateFormat(dateFormat);

    const measurementUnits = preferences.measurementUnits;
    storage.setMeasurementUnits(measurementUnits);

    const notificationDuration = preferences.notificationDuration;
    storage.setNotificationDuration(notificationDuration);

    const codeRecognitionEnabled = preferences.codeRecognitionEnabled;
    storage.setCodeRecognitionEnabled(codeRecognitionEnabled);

    const headerClockEnabled = preferences.headerClockEnabled;
    const clockSecondsEnabled = preferences.clockSecondsEnabled;
    storage.setClockPreferences(headerClockEnabled, clockSecondsEnabled);

    const soundEffects = preferences.soundEffects;
    storage.setSoundEffects(soundEffects);

    const liveStatusOverlayEnabled = preferences.liveStatusOverlayEnabled;
    storage.setLiveStatusOverlayEnabled(liveStatusOverlayEnabled);

    const theme = preferences.theme;
    storage.setTheme(theme);

    const accentColor = preferences.accentColor;
    storage.setAccentColor(accentColor);

    const surfaceColor = preferences.surfaceColor;
    storage.setSurfaceColor(surfaceColor);

    const reduceMotions = preferences.reduceMotions;
    storage.setReduceMotions(reduceMotions);

    const glassEnabled = preferences.glassEnabled;
    storage.setGlassEnabled(glassEnabled);

    const pageAnimation = preferences.pageAnimation;
    storage.setPageAnimation(pageAnimation);

    const modalAnimation = preferences.modalAnimation;
    storage.setModalAnimation(modalAnimation);

    const notificationAnimation = preferences.notificationAnimation;
    storage.setNotificationAnimation(notificationAnimation);

    const animationSpeed = preferences.animationSpeed;
    storage.setAnimationSpeed(animationSpeed);

    const interfaceScale = preferences.interfaceScale;
    storage.setInterfaceScale(interfaceScale);

    const wallpaperOverlay = preferences.wallpaperOverlay;
    storage.setWallpaperOverlay(wallpaperOverlay);

    const solidBackground = preferences.solidBackground;
    storage.setSolidBackground(solidBackground);

    const headerAutoHide = preferences.headerAutoHide;
    storage.setHeaderAutoHide(headerAutoHide);

    const showScrollToTopButton = preferences.showScrollToTopButton;
    storage.setShowScrollToTopButton(showScrollToTopButton);

    const showMainStatusIndicator = preferences.showMainStatusIndicator;
    storage.setShowMainStatusIndicator(showMainStatusIndicator);

    const dashboardLocked = preferences.dashboardLocked;
    storage.setDashboardLocked(dashboardLocked);

    const defaultPage = preferences.defaultPage;
    storage.setDefaultPage(defaultPage);

    const chartColorMode = preferences.chartColorMode;
    storage.setChartColorMode(chartColorMode);

    const chartStaticColor = preferences.chartStaticColor;
    storage.setChartStaticColor(chartStaticColor);

    manager.commitChanges();
    return solidBackgroundChanged;
};

export { commitUiPreferences };
