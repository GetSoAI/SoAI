/* SoAI - Shared storage presentation preferences actions [frontend/assets/ts/core/storage/service/presentationpreferences/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dispatchCustomEvent, getBody, getDocumentElement } from '@core/environment/public.ts';
import { ANIMATION_SPEED_ATTRIBUTE } from '@core/animations/speed.ts';
import { isAnimationSpeed, isAnimationType, isChartColorModeType } from '@core/storage/guards.ts';
import { normalizeModalState } from '@core/storage/modalState.ts';
import type { StorageRuntime } from '@core/storage/service/types.ts';
import type { ModalState } from '@core/storage/types.ts';
import { applyAccentColor, normalizeAccentColorPreference } from '@core/theme/accentColor.ts';
import { trimHexColorOrNull } from '@core/theme/hexColor.ts';
import { applySurfaceColor, normalizeSurfaceColorPreference } from '@core/theme/surfaceColor.ts';
import type { JsonValue, JsonObject } from '@core/types/jsonValues.ts';
import { isNumber, isObject, isString } from '@core/typeGuards.ts';
import { createChatPresentationPreferenceActions } from '@core/storage/service/presentationpreferences/chatActions.ts';
import { CHANGED_EVENTS } from '@core/storage/service/constants.ts';
import { applyInterfaceScaleAttribute, dispatchInterfaceScaleChanged, isInterfaceScalePercent } from '@core/layout/interfaceScale.ts';

const dispatch = (name: string, detail?: JsonObject): void => {
    dispatchCustomEvent(name, detail ?? null);
};

const createPresentationPreferenceActions = (
    core: StorageRuntime
): {
    setTerminalPreferences: (patch: JsonValue | null | undefined) => void;
    setTerminalTextZoom: (zoom: number) => void;
    setNotificationDuration: (duration: number) => void;
    setCodeRecognitionEnabled: (enabled: boolean) => void;
    setReduceMotions: (enabled: boolean) => void;
    setAccentColor: (color: string | null) => void;
    setSurfaceColor: (color: string | null) => void;
    setHeaderAutoHide: (enabled: boolean) => void;
    setShowScrollToTopButton: (enabled: boolean) => void;
    setGlassEnabled: (enabled: boolean) => void;
    setPageAnimation: (value: string) => void;
    setModalAnimation: (value: string) => void;
    setNotificationAnimation: (value: string) => void;
    setAnimationSpeed: (value: string) => void;
    setInterfaceScale: (value: number) => void;
    setSoundEffects: (enabled: boolean) => void;
    setLiveStatusOverlayEnabled: (enabled: boolean) => void;
    setModalState: (modalId: string, patch: ModalState) => void;
    clearModalState: (modalId: string) => void;
    clearAllModalStates: () => void;
    setWallpaperOverlay: (value: number) => void;
    setSolidBackground: (color: string | null) => void;
    setChartColorMode: (mode: string) => void;
    setChartStaticColor: (color: string) => void;
    setAdvancedMode: (enabled: boolean) => void;
    setChatWidescreenMode: (enabled: boolean) => void;
    setChatSidebarOpen: (open: boolean) => void;
    setChatShowFavoritesAtTop: (enabled: boolean) => void;
    setChatPlanBarVisible: (visible: boolean) => void;
    setAssistantAvatar: (value: string | null) => void;
    setUserAvatar: (value: string | null) => void;
} => {
    const state = core.state;
    const chatActions = createChatPresentationPreferenceActions(core);

    const setTerminalPreferences = (patch: JsonValue | null | undefined): void => {
        if (!isObject(patch)) {
            return;
        }
        const textZoom = patch['text_zoom'];
        if (isNumber(textZoom) && Number.isFinite(textZoom)) {
            state.cache.terminal.textZoom = core.normalizeZoom(textZoom, 0.5, 2);
            terminateHandledPromise(core.queuePersist('terminal'));
        }
    };

    const setTerminalTextZoom = (zoom: number): void => {
        const normalized = core.normalizeZoom(zoom, 0.5, 2);
        if (normalized !== state.cache.terminal.textZoom) {
            state.cache.terminal.textZoom = normalized;
            terminateHandledPromise(core.queuePersist('terminal'));
        }
    };

    const setNotificationDuration = (duration: number): void => {
        state.cache.ui.notificationDuration = isNumber(duration) ? duration : 3;
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch('soai:notificationduration:changed', { duration: state.cache.ui.notificationDuration });
    };

    const setCodeRecognitionEnabled = (enabled: boolean): void => {
        if (state.cache.ui.codeRecognitionEnabled === enabled) {
            return;
        }
        state.cache.ui.codeRecognitionEnabled = enabled;
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch(CHANGED_EVENTS.codeRecognition, { enabled });
    };

    const setReduceMotions = (enabled: boolean): void => {
        state.cache.ui.reduceMotions = !!enabled;
        terminateHandledPromise(core.queuePersist('ui'));
        core.bodyClass('reduce-motions', enabled);
        dispatch('soai:reducemotions:changed', { enabled: !!enabled });
    };

    const setAccentColor = (color: string | null): void => {
        const normalized = normalizeAccentColorPreference(color);
        state.cache.ui.accentColor = normalized;
        terminateHandledPromise(core.queuePersist('ui'));
        applyAccentColor({ root: getDocumentElement(), body: getBody() }, normalized);
        dispatch('soai:accentcolor:changed', { color: normalized });
    };

    const setSurfaceColor = (color: string | null): void => {
        const normalized = normalizeSurfaceColorPreference(color);
        state.cache.ui.surfaceColor = normalized;
        terminateHandledPromise(core.queuePersist('ui'));
        applySurfaceColor({ root: getDocumentElement(), body: getBody() }, normalized);
        dispatch('soai:surfacecolor:changed', { color: normalized });
    };

    const setHeaderAutoHide = (enabled: boolean): void => {
        const normalized = enabled !== false;
        if (state.cache.ui.headerAutoHide !== normalized) {
            state.cache.ui.headerAutoHide = normalized;
            terminateHandledPromise(core.queuePersist('ui'));
        }
        core.bodyClass('header-auto-hide-disabled', !normalized);
        dispatch('soai:header:autoHide:changed', { enabled: normalized });
    };

    const setShowScrollToTopButton = (enabled: boolean): void => {
        const normalized = enabled !== false;
        if (state.cache.ui.showScrollToTopButton !== normalized) {
            state.cache.ui.showScrollToTopButton = normalized;
            terminateHandledPromise(core.queuePersist('ui'));
        }
        core.bodyClass('scroll-top-action-disabled', !normalized);
        dispatch('soai:scrollToTop:changed', { enabled: normalized });
    };

    const setGlassEnabled = (enabled: boolean): void => {
        const normalized = enabled !== false;
        state.cache.ui.glassEnabled = normalized;
        terminateHandledPromise(core.queuePersist('ui'));
        core.setGlassDisabled(!normalized);
        dispatch('soai:glass:changed', { enabled: normalized });
    };

    const setPageAnimation = (value: string): void => {
        if (!isAnimationType(value)) {
            throw new Error('Page animation preference must be a valid animation type');
        }
        state.cache.ui.pageAnimation = value;
        terminateHandledPromise(core.queuePersist('ui'));
        core.setAttr('data-page-animation', value);
        dispatch('soai:animation:page:changed', { value });
    };

    const setModalAnimation = (value: string): void => {
        if (!isAnimationType(value)) {
            throw new Error('Modal animation preference must be a valid animation type');
        }
        state.cache.ui.modalAnimation = value;
        terminateHandledPromise(core.queuePersist('ui'));
        core.setAttr('data-modal-animation', value);
        dispatch('soai:animation:modal:changed', { value });
    };

    const setNotificationAnimation = (value: string): void => {
        if (!isAnimationType(value)) {
            throw new Error('Notification animation preference must be a valid animation type');
        }
        state.cache.ui.notificationAnimation = value;
        terminateHandledPromise(core.queuePersist('ui'));
        core.setAttr('data-notification-animation', value);
        dispatch('soai:animation:notification:changed', { value });
    };

    const setAnimationSpeed = (value: string): void => {
        if (!isAnimationSpeed(value)) {
            throw new Error('Animation speed preference must be a valid animation speed');
        }
        state.cache.ui.animationSpeed = value;
        terminateHandledPromise(core.queuePersist('ui'));
        core.setAttr(ANIMATION_SPEED_ATTRIBUTE, value);
        dispatch('soai:animation:speed:changed', { value });
    };

    const setInterfaceScale = (value: number): void => {
        if (!isInterfaceScalePercent(value)) {
            throw new TypeError('Interface scale preference must be one of the supported percentage steps');
        }
        const renderedScaleChanged = applyInterfaceScaleAttribute(getDocumentElement(), value, core.setAttr);
        const cacheChanged = state.cache.ui.interfaceScale !== value;
        state.cache.ui.interfaceScale = value;
        if (renderedScaleChanged) {
            dispatchInterfaceScaleChanged(value);
        }
        if (cacheChanged) {
            terminateHandledPromise(core.queuePersist('ui'));
        }
    };

    const setSoundEffects = (enabled: boolean): void => {
        state.cache.ui.soundEffects = !!enabled;
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch('soai:soundeffects:changed', { enabled: !!enabled });
    };

    const setLiveStatusOverlayEnabled = (enabled: boolean): void => {
        const normalized = !!enabled;
        if (state.cache.ui.liveStatusOverlayEnabled !== normalized) {
            state.cache.ui.liveStatusOverlayEnabled = normalized;
            terminateHandledPromise(core.queuePersist('ui'));
            dispatch('soai:liveStatusOverlay:changed', { enabled: normalized });
        }
    };

    const clearAllModalStates = (): void => {
        state.cache.ui.modalStates = {};
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const setModalState = (modalId: string, patch: ModalState): void => {
        if (!isString(modalId) || !modalId.trim()) {
            throw new Error('modalId must be a string');
        }
        if (!isObject(patch)) {
            throw new TypeError('Modal state must be an object');
        }
        const trimmed = modalId.trim();
        const existingState = normalizeModalState(state.cache.ui.modalStates[trimmed]) ?? {};
        state.cache.ui.modalStates[trimmed] = { ...existingState, ...core.clone(patch) };
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const clearModalState = (modalId: string): void => {
        if (modalId && state.cache.ui.modalStates) {
            delete state.cache.ui.modalStates[modalId];
            terminateHandledPromise(core.queuePersist('ui'));
        }
    };

    const setWallpaperOverlay = (value: number): void => {
        state.cache.ui.wallpaperOverlay = isNumber(value) ? value : 0;
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const setSolidBackground = (color: string | null): void => {
        state.cache.ui.solidBackground = color || null;
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const setChartColorMode = (mode: string): void => {
        const normalized = isChartColorModeType(mode) ? mode : 'auto';
        state.cache.ui.chartColorMode = normalized;
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch('soai:chartcolors:changed', { mode: normalized });
    };

    const setChartStaticColor = (color: string): void => {
        const normalized = trimHexColorOrNull(color) ?? '#4ade80';
        state.cache.ui.chartStaticColor = normalized;
        terminateHandledPromise(core.queuePersist('ui'));
        dispatch('soai:chartcolors:changed', { staticColor: normalized });
    };

    const setAdvancedMode = (enabled: boolean): void => {
        state.cache.settings.advancedMode = !!enabled;
        terminateHandledPromise(core.queuePersist('settings'));
    };

    return {
        setTerminalPreferences,
        setTerminalTextZoom,
        setNotificationDuration,
        setCodeRecognitionEnabled,
        setReduceMotions,
        setAccentColor,
        setSurfaceColor,
        setHeaderAutoHide,
        setShowScrollToTopButton,
        setGlassEnabled,
        setPageAnimation,
        setModalAnimation,
        setNotificationAnimation,
        setAnimationSpeed,
        setInterfaceScale,
        setSoundEffects,
        setLiveStatusOverlayEnabled,
        setModalState,
        clearModalState,
        clearAllModalStates,
        setWallpaperOverlay,
        setSolidBackground,
        setChartColorMode,
        setChartStaticColor,
        setAdvancedMode,
        ...chatActions
    };
};

export { createPresentationPreferenceActions };
