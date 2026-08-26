/* SoAI - Shared storage presentation preferences state [frontend/assets/ts/core/storage/service/presentationpreferences/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeModalState } from '@core/storage/modalState.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';
import type { AnimationSpeed, AnimationType, ChartColorModeType, ModalState, TerminalCache } from '@core/storage/types.ts';
import { isString } from '@core/typeGuards.ts';
import type { InterfaceScalePercent } from '@core/layout/interfaceScale.ts';

const createPresentationPreferenceState = (
    core: StorageRuntime
): {
    getTerminalPreferences: () => TerminalCache;
    getTerminalTextZoom: (defaultZoom?: number) => number;
    getNotificationDuration: () => number;
    getCodeRecognitionEnabled: () => boolean;
    getReduceMotions: () => boolean;
    getAccentColor: () => string | null;
    getSurfaceColor: () => string | null;
    getHeaderAutoHide: () => boolean;
    getShowScrollToTopButton: () => boolean;
    getGlassEnabled: () => boolean;
    getPageAnimation: () => AnimationType;
    getModalAnimation: () => AnimationType;
    getNotificationAnimation: () => AnimationType;
    getAnimationSpeed: () => AnimationSpeed;
    getInterfaceScale: () => InterfaceScalePercent;
    getSoundEffects: () => boolean;
    getLiveStatusOverlayEnabled: () => boolean;
    getModalState: (modalId: string) => ModalState | null;
    getWallpaperOverlay: () => number;
    getSolidBackground: () => string | null;
    getChartColorMode: () => ChartColorModeType;
    getChartStaticColor: () => string;
    getAdvancedMode: () => boolean;
    getChatWidescreenMode: () => boolean;
    getChatSidebarOpen: () => boolean;
    getChatShowFavoritesAtTop: () => boolean;
    getChatPlanBarVisible: () => boolean;
    getAssistantAvatar: () => string | null;
    getUserAvatar: () => string | null;
} => {
    const state = core.state;

    const getTerminalPreferences = (): TerminalCache => core.clone(state.cache.terminal);

    const getTerminalTextZoom = (defaultZoom: number = state.defaults.terminal.textZoom): number => {
        return state.cache.terminal.textZoom ?? defaultZoom;
    };

    const getNotificationDuration = (): number => state.cache.ui.notificationDuration;

    const getCodeRecognitionEnabled = (): boolean => state.cache.ui.codeRecognitionEnabled;

    const getReduceMotions = (): boolean => !!state.cache.ui.reduceMotions;

    const getAccentColor = (): string | null => state.cache.ui.accentColor;

    const getSurfaceColor = (): string | null => state.cache.ui.surfaceColor;

    const getHeaderAutoHide = (): boolean => state.cache.ui.headerAutoHide !== false;

    const getShowScrollToTopButton = (): boolean => state.cache.ui.showScrollToTopButton !== false;

    const getGlassEnabled = (): boolean => state.cache.ui.glassEnabled !== false;

    const getPageAnimation = (): AnimationType => state.cache.ui.pageAnimation;

    const getModalAnimation = (): AnimationType => state.cache.ui.modalAnimation;

    const getNotificationAnimation = (): AnimationType => state.cache.ui.notificationAnimation;

    const getAnimationSpeed = (): AnimationSpeed => state.cache.ui.animationSpeed;

    const getInterfaceScale = (): InterfaceScalePercent => state.cache.ui.interfaceScale;

    const getSoundEffects = (): boolean => !!state.cache.ui.soundEffects;

    const getLiveStatusOverlayEnabled = (): boolean => !!state.cache.ui.liveStatusOverlayEnabled;

    const getModalState = (modalId: string): ModalState | null => {
        if (!isString(modalId) || !modalId.trim()) {
            throw new Error('modalId must be a string');
        }
        const existing = state.cache.ui.modalStates[modalId.trim()];
        const normalized = normalizeModalState(existing);
        return normalized ? core.clone(normalized) : null;
    };

    const getWallpaperOverlay = (): number => state.cache.ui.wallpaperOverlay;

    const getSolidBackground = (): string | null => state.cache.ui.solidBackground;

    const getChartColorMode = (): ChartColorModeType => state.cache.ui.chartColorMode || 'auto';

    const getChartStaticColor = (): string => state.cache.ui.chartStaticColor || '#4ade80';

    const getAdvancedMode = (): boolean => !!state.cache.settings.advancedMode;

    const getChatWidescreenMode = (): boolean => !!state.cache.chat.widescreenMode;

    const getChatSidebarOpen = (): boolean => state.cache.chat.sidebarOpen === true;

    const getChatShowFavoritesAtTop = (): boolean => state.cache.chat.showFavoritesAtTop === true;

    const getChatPlanBarVisible = (): boolean => state.cache.chat.planBarVisible === true;

    const getAssistantAvatar = (): string | null => state.cache.chat.assistantAvatar || null;

    const getUserAvatar = (): string | null => state.cache.chat.userAvatar || null;

    return {
        getTerminalPreferences,
        getTerminalTextZoom,
        getNotificationDuration,
        getCodeRecognitionEnabled,
        getReduceMotions,
        getAccentColor,
        getSurfaceColor,
        getHeaderAutoHide,
        getShowScrollToTopButton,
        getGlassEnabled,
        getPageAnimation,
        getModalAnimation,
        getNotificationAnimation,
        getAnimationSpeed,
        getInterfaceScale,
        getSoundEffects,
        getLiveStatusOverlayEnabled,
        getModalState,
        getWallpaperOverlay,
        getSolidBackground,
        getChartColorMode,
        getChartStaticColor,
        getAdvancedMode,
        getChatWidescreenMode,
        getChatSidebarOpen,
        getChatShowFavoritesAtTop,
        getChatPlanBarVisible,
        getAssistantAvatar,
        getUserAvatar
    };
};

export { createPresentationPreferenceState };
