/* SoAI - Lifetime-bound UI preference reset mutation ownership [frontend/assets/ts/core/storage/service/preferences/preferenceReset.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError } from '@core/errors/abort.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { PreferenceDelegates } from '@core/storage/service/preferences/types.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';
import type { UiPreferences } from '@core/storage/types.ts';

interface ResetOptions {
    preserveWizardState?: boolean | undefined;
    canApply?: () => boolean;
}

interface PreferenceResetMutations extends PreferenceDelegates {
    setTheme(preference: string): string;
    clearAllModalStates(): void;
}

const resetUiPreferences = (core: StorageRuntime, mutations: PreferenceResetMutations, options: ResetOptions = {}): UiPreferences => {
    const canApply = options.canApply ?? (() => true);
    const requireCurrent = (): void => {
        if (!canApply()) throw createAbortError('Preference reset is no longer current');
    };
    requireCurrent();
    const defaults = core.createDefaults();
    const preservedWizard = options.preserveWizardState !== false ? core.state.cache.wizard : defaults.wizard;
    const preservedMisc = core.state.cache.misc;
    const operations: readonly (() => void)[] = [
        () => mutations.setTheme(defaults.ui.theme),
        () => mutations.setLanguage(defaults.ui.language),
        () => mutations.setClockFormat(defaults.ui.clockFormat),
        () => mutations.setRegionalLocale(defaults.ui.regionalLocale),
        () => mutations.setDateFormat(defaults.ui.dateFormat),
        () => mutations.setMeasurementUnits(defaults.ui.measurementUnits),
        () => mutations.setNotificationDuration(defaults.ui.notificationDuration),
        () => mutations.setCodeRecognitionEnabled(defaults.ui.codeRecognitionEnabled),
        () => mutations.setClockPreferences(defaults.ui.headerClockEnabled, defaults.ui.clockSecondsEnabled),
        () => mutations.setPromptEnhancerModel(defaults.ui.promptEnhancerModel),
        () => mutations.setReduceMotions(defaults.ui.reduceMotions),
        () => mutations.setAccentColor(defaults.ui.accentColor),
        () => mutations.setSurfaceColor(defaults.ui.surfaceColor),
        () => mutations.setSoundEffects(defaults.ui.soundEffects),
        () => mutations.setLiveStatusOverlayEnabled(defaults.ui.liveStatusOverlayEnabled),
        () => mutations.setGlassEnabled(defaults.ui.glassEnabled),
        () => mutations.setWallpaperOverlay(defaults.ui.wallpaperOverlay),
        () => mutations.setSolidBackground(defaults.ui.solidBackground),
        () => mutations.setDefaultWallpaper(defaults.ui.defaultWallpaper),
        () => mutations.setChartColorMode(defaults.ui.chartColorMode),
        () => mutations.setChartStaticColor(defaults.ui.chartStaticColor),
        () => mutations.setHiddenSidebarPages(defaults.ui.hiddenSidebarPages),
        () => mutations.setHiddenDashboardElements(defaults.ui.hiddenDashboardElements),
        () => mutations.setDashboardLocked(defaults.ui.dashboardLocked),
        () => mutations.setDashboardImageCard(defaults.ui.dashboardImageCard),
        () => mutations.setDashboardImageCardFit(defaults.ui.dashboardImageCardFit),
        () => mutations.setDashboardMemo(defaults.ui.dashboardMemo),
        () => mutations.setDefaultPage(defaults.ui.defaultPage),
        () => mutations.setHeaderAutoHide(defaults.ui.headerAutoHide),
        () => mutations.setShowScrollToTopButton(defaults.ui.showScrollToTopButton),
        () => mutations.setShowMainStatusIndicator(defaults.ui.showMainStatusIndicator),
        () => mutations.setPageAnimation(defaults.ui.pageAnimation),
        () => mutations.setModalAnimation(defaults.ui.modalAnimation),
        () => mutations.setNotificationAnimation(defaults.ui.notificationAnimation),
        () => mutations.setAnimationSpeed(defaults.ui.animationSpeed),
        () => mutations.setInterfaceScale(defaults.ui.interfaceScale),
        () => mutations.clearAllModalStates()
    ];
    for (const operation of operations) {
        requireCurrent();
        operation();
    }
    requireCurrent();
    core.state.cache.ui.mainStatePreferenceVersion = defaults.ui.mainStatePreferenceVersion;
    core.state.cache.chat.preferences = core.clone(defaults.chat.preferences);
    core.state.cache.chat.defaultEmbeddingModel = defaults.chat.defaultEmbeddingModel ?? null;
    core.state.cache.chat.textZoom = defaults.chat.textZoom;
    core.state.cache.logs = core.clone(defaults.logs);
    core.state.cache.terminal = core.clone(defaults.terminal);
    core.state.cache.search = core.clone(defaults.search);
    core.state.cache.hardware = core.clone(defaults.hardware);
    core.state.cache.filters = core.clone(defaults.filters);
    core.state.cache.wizard = { completed: preservedWizard.completed, aiSetup: null };
    core.state.cache.settings = core.clone(defaults.settings);
    core.state.cache.misc = core.clone(preservedMisc);
    const resetGroups: readonly string[] = ['chat', 'logs', 'terminal', 'search', 'hardware', 'filters', 'wizard', 'settings', 'misc'];
    for (const group of resetGroups) {
        requireCurrent();
        terminateHandledPromise(core.queuePersist(group));
    }
    core.scheduleBroadcast();
    requireCurrent();
    return core.clone(core.state.cache.ui);
};

export { resetUiPreferences };
export type { ResetOptions };
