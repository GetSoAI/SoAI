/* SoAI - Shared storage service state [frontend/assets/ts/core/storage/service/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StorageRuntime } from '@core/storage/service/types.ts';
import { normalizeNonBlankStringOrNull } from '@core/storage/normalization.ts';
import type { ClockFormatType, HardwareCache, ImageFitType, LogsCache, SessionData } from '@core/storage/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const createStorageStateReaders = (core: StorageRuntime): { getChatTextZoom: (fallback?: number) => number; getRecentSearches: () => string[]; getHardwarePreferences: () => HardwareCache; getGPUSettings: (id: string) => JsonValue; getSession: () => SessionData; getRedirectAfterLogin: () => string | null; isWizardCompletionPending: () => boolean; isWizardCompleted: () => boolean; getClockFormat: () => ClockFormatType; getLanguage: () => string; getHiddenSidebarPages: () => string[]; getShowMainStatusIndicator: () => boolean; getHiddenDashboardElements: () => string[]; getDashboardLocked: () => boolean; getDashboardImageCard: () => string | null; getDashboardImageCardFit: () => ImageFitType; getDashboardMemo: () => string | null; getDefaultPage: () => string | null; getLogsPreferences: () => LogsCache; getLogLineLimit: (fallback?: number) => number; getLogsTextZoom: (fallback?: number) => number } => {
    const state = core.state;
    const getChatTextZoom = (fallback: number = state.defaults.chat.textZoom): number => {
        return state.cache.chat.textZoom ?? fallback;
    };
    const getRecentSearches = (): string[] => state.cache.search.recent.slice();
    const getHardwarePreferences = (): HardwareCache => core.clone(state.cache.hardware);
    const getGPUSettings = (id: string): JsonValue => {
        if (!state.cache.hardware.gpuSettings[id]) {
            throw new Error(`Unknown GPU id ${id}`);
        }
        return core.clone(state.cache.hardware.gpuSettings[id]);
    };

    const getSession = (): SessionData => core.clone(state.session);

    const getRedirectAfterLogin = (): string | null => state.redirectAfterLogin || null;
    const isWizardCompletionPending = (): boolean => state.session['wizard_completion_pending'] === true;

    const isWizardCompleted = (): boolean => state.cache.wizard.completed === true;

    const getClockFormat = (): ClockFormatType => state.cache.ui.clockFormat;
    const getLanguage = (): string => state.cache.ui.language?.trim() || 'en';
    const getHiddenSidebarPages = (): string[] => [...(state.cache.ui.hiddenSidebarPages || state.defaults.ui.hiddenSidebarPages)];
    const getShowMainStatusIndicator = (): boolean => state.cache.ui.showMainStatusIndicator ?? state.defaults.ui.showMainStatusIndicator;
    const getHiddenDashboardElements = (): string[] => [...(state.cache.ui.hiddenDashboardElements || state.defaults.ui.hiddenDashboardElements)];
    const getDashboardLocked = (): boolean => state.cache.ui.dashboardLocked ?? state.defaults.ui.dashboardLocked;
    const getDashboardImageCard = (): string | null => state.cache.ui.dashboardImageCard ?? state.defaults.ui.dashboardImageCard;
    const getDashboardImageCardFit = (): ImageFitType => state.cache.ui.dashboardImageCardFit ?? state.defaults.ui.dashboardImageCardFit;
    const getDashboardMemo = (): string | null => normalizeNonBlankStringOrNull(state.cache.ui.dashboardMemo ?? state.defaults.ui.dashboardMemo);
    const getDefaultPage = (): string | null => normalizeNonBlankStringOrNull(state.cache.ui.defaultPage ?? state.defaults.ui.defaultPage);

    const getLogsPreferences = (): LogsCache => core.clone(state.cache.logs);
    const getLogLineLimit = (fallback: number = state.defaults.logs.lineLimit): number => {
        const current = state.cache.logs.lineLimit;
        return Number.isFinite(current) ? current : fallback;
    };
    const getLogsTextZoom = (fallback: number = state.defaults.logs.textZoom): number => {
        const current = state.cache.logs.textZoom;
        return Number.isFinite(current) ? current : fallback;
    };

    return {
        getChatTextZoom,
        getRecentSearches,
        getHardwarePreferences,
        getGPUSettings,
        getSession,
        getRedirectAfterLogin,
        isWizardCompletionPending,
        isWizardCompleted,
        getClockFormat,
        getLanguage,
        getHiddenSidebarPages,
        getShowMainStatusIndicator,
        getHiddenDashboardElements,
        getDashboardLocked,
        getDashboardImageCard,
        getDashboardImageCardFit,
        getDashboardMemo,
        getDefaultPage,
        getLogsPreferences,
        getLogLineLimit,
        getLogsTextZoom
    };
};

export { createStorageStateReaders };
