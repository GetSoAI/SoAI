/* SoAI - Shared storage preferences contracts [frontend/assets/ts/core/storage/service/preferences/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageApiClientContract, StorageRuntime } from '@core/storage/service/types.ts';
import type { DateFormatPreference, MeasurementUnitsPreference, RegionalLocalePreference } from '@core/localization/public.ts';
import type { ChatPreferencesManager, ImageFitType, ThemeType, UiPreferences } from '@core/storage/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { InterfaceScalePercent } from '@core/layout/interfaceScale.ts';

interface PreferenceDelegates {
    setLanguage(language: string): void;
    setClockFormat(format: '24h' | '12h'): void;
    setRegionalLocale(locale: RegionalLocalePreference): void;
    setDateFormat(format: DateFormatPreference): void;
    setMeasurementUnits(units: MeasurementUnitsPreference): void;
    setNotificationDuration(duration: number): void;
    setCodeRecognitionEnabled(enabled: boolean): void;
    setClockPreferences(headerClockEnabled: boolean, clockSecondsEnabled: boolean): void;
    setReduceMotions(enabled: boolean): void;
    setAccentColor(color: string | null): void;
    setSurfaceColor(color: string | null): void;
    setSoundEffects(enabled: boolean): void;
    setLiveStatusOverlayEnabled(enabled: boolean): void;
    setWallpaperOverlay(value: number): void;
    setSolidBackground(color: string | null): void;
    setGlassEnabled(enabled: boolean): void;
    setHiddenSidebarPages(pages: string[]): void;
    setShowMainStatusIndicator(enabled: boolean): void;
    setHiddenDashboardElements(elements: string[]): void;
    setDashboardLocked(locked: boolean): void;
    setDashboardImageCard(value: string | null): void;
    setDashboardImageCardFit(fit: ImageFitType): void;
    setDashboardMemo(value: string | null): void;
    setChartColorMode(mode: string): void;
    setChartStaticColor(color: string): void;
    setHeaderAutoHide(enabled: boolean): void;
    setShowScrollToTopButton(enabled: boolean): void;
    setPageAnimation(value: string): void;
    setModalAnimation(value: string): void;
    setNotificationAnimation(value: string): void;
    setAnimationSpeed(value: string): void;
    setInterfaceScale(value: InterfaceScalePercent): void;
    setPromptEnhancerModel(value: string | null): void;
}

type PreferenceHandler = (value: JsonValue | null | undefined) => void;

interface StoragePreferenceMethods {
    refresh(options?: { authTransitionOwned?: boolean }): Promise<void>;
    setAuthenticated(authenticated: boolean, options?: { authTransitionOwned?: boolean }): Promise<void>;
    getPreferences(): UiPreferences;
    setPreferences(patch: JsonObject | null | undefined): UiPreferences;
    setPreference(keyCandidate: string, value: JsonValue | null | undefined): UiPreferences;
    getTheme(): ThemeType;
    setTheme(preference: string): string;
    toggleTheme(): string;
    saveDashboardLayout(layout: JsonObject | null | undefined): void;
    getDashboardLayout(): JsonObject | null;
    getChatPreferences(): ChatPreferencesManager;
    getPromptEnhancerModel(): string | null;
    setPromptEnhancerModel(value: string | null): UiPreferences;
}

interface PreferenceHandlerContext {
    core: StorageRuntime;
    delegates: PreferenceDelegates;
    setTheme(preference: string): string;
    saveDashboardLayout(layout: JsonObject | null | undefined): void;
}

export type { PreferenceDelegates, PreferenceHandler, PreferenceHandlerContext, StorageApiClientContract, StorageRuntime, StoragePreferenceMethods };
