/* SoAI - Settings page UI preferences [frontend/assets/ts/pages/settings/controllers/page/uiPreferences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import { createUiPrefsSnapshot } from '@pages/settings/controllers/page/loadDataMappers.ts';
import { isHexColorString } from '@core/theme/hexColor.ts';
import type { SettingsUiPreferenceHost } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { requireUiPrefsAnimation, requireUiPrefsAnimationSpeed, requireUiPrefsBoolean, requireUiPrefsChartColorMode, requireUiPrefsClockFormat, requireUiPrefsDateFormat, requireUiPrefsInterfaceScale, requireUiPrefsLanguage, requireUiPrefsMeasurementUnits, requireUiPrefsNonEmptyString, requireUiPrefsNotificationDuration, requireUiPrefsNullableString, requireUiPrefsRegionalLocale, requireUiPrefsTheme, requireUiPrefsWallpaperOverlay } from '@pages/settings/controllers/uiprefs/guards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { SaveUnitResult } from '@core/save/public.ts';
import { normalizeClockPreferenceState } from '@core/storage/clockPreferences.ts';

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
    headerAutoHide: requireUiPrefsBoolean(current['headerAutoHide'], 'uiPrefs.headerAutoHide'),
    showScrollToTopButton: requireUiPrefsBoolean(current['showScrollToTopButton'], 'uiPrefs.showScrollToTopButton'),
    showMainStatusIndicator: requireUiPrefsBoolean(current['showMainStatusIndicator'], 'uiPrefs.showMainStatusIndicator'),
    dashboardLocked: requireUiPrefsBoolean(current['dashboardLocked'], 'uiPrefs.dashboardLocked'),
    defaultPage: requireUiPrefsNullableString(current['defaultPage'], 'uiPrefs.defaultPage'),
    chartColorMode: requireUiPrefsChartColorMode(current['chartColorMode']),
    chartStaticColor: requireHexColor(current['chartStaticColor'], 'uiPrefs.chartStaticColor', false)
});

type UiPreferenceSnapshot = ReturnType<typeof readUiPreferencesForCommit>;
interface PartialUiPreferencesCommit {
    type: 'partial';
    appliedFields: readonly UiPreferenceKey[];
    pendingFields: readonly UiPreferenceKey[];
    error: Error;
}

interface PreparedUiPreferences {
    preferences: UiPreferenceSnapshot;
    edited: ReadonlySet<UiPreferenceKey>;
    isCurrent: () => boolean;
}

const prepareUiPreferences = (state: Pick<SettingsPageState, 'uiPrefsManager'>, isCurrent: () => boolean = () => true): PreparedUiPreferences | null => {
    const manager = state.uiPrefsManager;
    if (!manager || !manager.hasChanges) return null;
    const preferences = readUiPreferencesForCommit(manager.currentData);
    const baseline = manager.originalData;
    const edited = new Set<UiPreferenceKey>();
    const capture = (key: UiPreferenceKey): void => {
        if (!manager.areValuesEqual(preferences[key], baseline[key])) edited.add(key);
    };
    capture('language');
    capture('promptEnhancerModel');
    capture('clockFormat');
    capture('regionalLocale');
    capture('dateFormat');
    capture('measurementUnits');
    capture('notificationDuration');
    capture('codeRecognitionEnabled');
    capture('headerClockEnabled');
    capture('clockSecondsEnabled');
    capture('soundEffects');
    capture('liveStatusOverlayEnabled');
    capture('theme');
    capture('accentColor');
    capture('surfaceColor');
    capture('reduceMotions');
    capture('glassEnabled');
    capture('pageAnimation');
    capture('modalAnimation');
    capture('notificationAnimation');
    capture('animationSpeed');
    capture('interfaceScale');
    capture('wallpaperOverlay');
    capture('headerAutoHide');
    capture('showScrollToTopButton');
    capture('showMainStatusIndicator');
    capture('dashboardLocked');
    capture('defaultPage');
    capture('chartColorMode');
    capture('chartStaticColor');
    return { preferences, edited, isCurrent };
};

const commitUiPreferences = async (page: SettingsUiPreferenceHost, state: Pick<SettingsPageState, 'uiPrefsManager'>, prepared: PreparedUiPreferences | null = prepareUiPreferences(state)): Promise<SaveUnitResult | PartialUiPreferencesCommit> => {
    const manager = state.uiPrefsManager;
    if (!manager || !prepared) return;
    const { preferences, edited, isCurrent } = prepared;
    if (!isCurrent()) return { type: 'stop' };
    const storage = page.owners.storage;
    const appliedFields: UiPreferenceKey[] = [];
    try {
        if (edited.has('language')) {
            await page.owners.languageService.setLanguage(preferences.language, isCurrent);
            if (!isCurrent() || !page.owners.languageService.isLanguageRequestSettled(preferences.language)) return { type: 'stop' };
            manager.commitBaselinePatch({ language: page.owners.languageService.getLanguage() }, preferences);
            appliedFields.push('language');
        } else {
            manager.mergeRemotePatch({ language: page.owners.languageService.getLanguage() });
        }
        const operations: readonly [UiPreferenceKey, () => void][] = [
            ['promptEnhancerModel', () => storage.setPromptEnhancerModel(preferences.promptEnhancerModel)],
            ['clockFormat', () => storage.setClockFormat(preferences.clockFormat)],
            ['regionalLocale', () => storage.setRegionalLocale(preferences.regionalLocale)],
            ['dateFormat', () => storage.setDateFormat(preferences.dateFormat)],
            ['measurementUnits', () => storage.setMeasurementUnits(preferences.measurementUnits)],
            ['notificationDuration', () => storage.setNotificationDuration(preferences.notificationDuration)],
            ['codeRecognitionEnabled', () => storage.setCodeRecognitionEnabled(preferences.codeRecognitionEnabled)],
            ['soundEffects', () => storage.setSoundEffects(preferences.soundEffects)],
            ['liveStatusOverlayEnabled', () => storage.setLiveStatusOverlayEnabled(preferences.liveStatusOverlayEnabled)],
            ['theme', () => storage.setTheme(preferences.theme)],
            ['accentColor', () => storage.setAccentColor(preferences.accentColor)],
            ['surfaceColor', () => storage.setSurfaceColor(preferences.surfaceColor)],
            ['reduceMotions', () => storage.setReduceMotions(preferences.reduceMotions)],
            ['glassEnabled', () => storage.setGlassEnabled(preferences.glassEnabled)],
            ['pageAnimation', () => storage.setPageAnimation(preferences.pageAnimation)],
            ['modalAnimation', () => storage.setModalAnimation(preferences.modalAnimation)],
            ['notificationAnimation', () => storage.setNotificationAnimation(preferences.notificationAnimation)],
            ['animationSpeed', () => storage.setAnimationSpeed(preferences.animationSpeed)],
            ['interfaceScale', () => storage.setInterfaceScale(preferences.interfaceScale)],
            ['wallpaperOverlay', () => storage.setWallpaperOverlay(preferences.wallpaperOverlay)],
            ['headerAutoHide', () => storage.setHeaderAutoHide(preferences.headerAutoHide)],
            ['showScrollToTopButton', () => storage.setShowScrollToTopButton(preferences.showScrollToTopButton)],
            ['showMainStatusIndicator', () => storage.setShowMainStatusIndicator(preferences.showMainStatusIndicator)],
            ['dashboardLocked', () => storage.setDashboardLocked(preferences.dashboardLocked)],
            ['defaultPage', () => storage.setDefaultPage(preferences.defaultPage)],
            ['chartColorMode', () => storage.setChartColorMode(preferences.chartColorMode)],
            ['chartStaticColor', () => storage.setChartStaticColor(preferences.chartStaticColor)]
        ];
        for (const [field, persist] of operations) {
            if (!edited.has(field)) continue;
            if (!isCurrent()) return { type: 'stop' };
            persist();
            if (!isCurrent()) return { type: 'stop' };
            manager.commitBaselinePatch({ [field]: createUiPrefsSnapshot(page)[field] }, preferences);
            appliedFields.push(field);
        }
        if (edited.has('headerClockEnabled') || edited.has('clockSecondsEnabled')) {
            if (!isCurrent()) return { type: 'stop' };
            const clock = normalizeClockPreferenceState({
                headerClockEnabled: edited.has('headerClockEnabled') ? preferences.headerClockEnabled : storage.getHeaderClockEnabled(),
                clockSecondsEnabled: edited.has('clockSecondsEnabled') ? preferences.clockSecondsEnabled : storage.getClockSecondsEnabled()
            });
            storage.setClockPreferences(clock.headerClockEnabled, clock.clockSecondsEnabled);
            if (!isCurrent()) return { type: 'stop' };
            const patch: JsonObject = { headerClockEnabled: storage.getHeaderClockEnabled(), clockSecondsEnabled: storage.getClockSecondsEnabled() };
            manager.commitBaselinePatch(patch, preferences);
            if (edited.has('headerClockEnabled')) appliedFields.push('headerClockEnabled');
            if (edited.has('clockSecondsEnabled')) appliedFields.push('clockSecondsEnabled');
        }
    } catch (error) {
        const failure = ensureError(error);
        if (!isCurrent()) return { type: 'stop' };
        if (appliedFields.length === 0) throw failure;
        return { type: 'partial', appliedFields, pendingFields: Array.from(edited).filter((field) => !appliedFields.includes(field)), error: failure };
    }
};

export { commitUiPreferences, prepareUiPreferences };
export type { PreparedUiPreferences };
