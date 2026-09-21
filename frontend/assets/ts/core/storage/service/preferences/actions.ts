/* SoAI - Shared storage preferences actions [frontend/assets/ts/core/storage/service/preferences/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { normalizeModalStatesRecord } from '@core/storage/modalState.ts';
import { isChartColorModeType, isClockFormatType, isDateFormatPreference, isImageFitType, isInterfaceScalePercent, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/storage/guards.ts';
import { normalizeStringArray } from '@core/storage/normalization.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isBoolean, isNumber, isString } from '@core/typeGuards.ts';
import type { PreferenceHandler, PreferenceHandlerContext } from '@core/storage/service/preferences/types.ts';

const warnInvalidPreference = (key: string, value: JsonValue | null | undefined): void => {
    errorHandler.warn('StorageManager', `Invalid ${key} preference value`, value);
};

const createPreferenceHandlers = ({ core, delegates, setTheme, saveDashboardLayout }: PreferenceHandlerContext): Record<string, PreferenceHandler> => {
    const state = core.state;
    return {
        theme: (value: JsonValue | null | undefined): void => {
            if (isString(value)) {
                setTheme(value);
                return;
            }
            warnInvalidPreference('theme', value);
        },
        accentColor: (value: JsonValue | null | undefined): void => {
            if (value === null || value === undefined || isString(value)) {
                delegates.setAccentColor(value === undefined ? null : value);
                return;
            }
            warnInvalidPreference('accent_color', value);
        },
        surfaceColor: (value: JsonValue | null | undefined): void => {
            if (value === null || value === undefined || isString(value)) {
                delegates.setSurfaceColor(value === undefined ? null : value);
                return;
            }
            warnInvalidPreference('surface_color', value);
        },
        promptEnhancerModel: (value: JsonValue | null | undefined): void => {
            if (value === null || value === undefined || isString(value)) {
                delegates.setPromptEnhancerModel(value === undefined ? null : value);
                return;
            }
            warnInvalidPreference('prompt_enhancer_model', value);
        },
        dashboardLayout: (value: JsonValue | null | undefined): void => {
            saveDashboardLayout(isJsonObject(value) ? value : null);
        },
        interfaceScale: (value: JsonValue | null | undefined): void => {
            if (isInterfaceScalePercent(value)) {
                delegates.setInterfaceScale(value);
                return;
            }
            warnInvalidPreference('interface_scale', value);
        },
        language: (value: JsonValue | null | undefined): void => {
            if (isString(value) && value.trim()) {
                delegates.setLanguage(value);
                return;
            }
            warnInvalidPreference('language', value);
        },
        clockFormat: (value: JsonValue | null | undefined): void => {
            if (isClockFormatType(value)) {
                delegates.setClockFormat(value);
                return;
            }
            warnInvalidPreference('clock_format', value);
        },
        regionalLocale: (value: JsonValue | null | undefined): void => {
            if (isRegionalLocalePreference(value)) {
                delegates.setRegionalLocale(value);
                return;
            }
            warnInvalidPreference('regional_locale', value);
        },
        dateFormat: (value: JsonValue | null | undefined): void => {
            if (isDateFormatPreference(value)) {
                delegates.setDateFormat(value);
                return;
            }
            warnInvalidPreference('date_format', value);
        },
        measurementUnits: (value: JsonValue | null | undefined): void => {
            if (isMeasurementUnitsPreference(value)) {
                delegates.setMeasurementUnits(value);
                return;
            }
            warnInvalidPreference('measurement_units', value);
        },
        notificationDuration: (value: JsonValue | null | undefined): void => {
            if (isNumber(value) && Number.isFinite(value)) {
                delegates.setNotificationDuration(value);
                return;
            }
            warnInvalidPreference('notification_duration', value);
        },
        codeRecognitionEnabled: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setCodeRecognitionEnabled(value);
                return;
            }
            warnInvalidPreference('code_recognition_enabled', value);
        },
        headerClockEnabled: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setClockPreferences(value, state.cache.ui.clockSecondsEnabled === true);
                return;
            }
            warnInvalidPreference('header_clock_enabled', value);
        },
        clockSecondsEnabled: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setClockPreferences(state.cache.ui.headerClockEnabled !== false, value);
                return;
            }
            warnInvalidPreference('clock_seconds_enabled', value);
        },
        reduceMotions: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setReduceMotions(value);
                return;
            }
            warnInvalidPreference('reduce_motions', value);
        },
        soundEffects: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setSoundEffects(value);
                return;
            }
            warnInvalidPreference('sound_effects', value);
        },
        liveStatusOverlayEnabled: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setLiveStatusOverlayEnabled(value);
                return;
            }
            warnInvalidPreference('live_status_overlay_enabled', value);
        },
        modalStates: (value: JsonValue | null | undefined): void => {
            const modalStates = normalizeModalStatesRecord(value);
            if (modalStates !== null) {
                state.cache.ui.modalStates = modalStates;
                terminateHandledPromise(core.queuePersist('ui'));
                return;
            }
            warnInvalidPreference('modal_states', value);
        },
        wallpaperOverlay: (value: JsonValue | null | undefined): void => {
            if (isNumber(value) && Number.isFinite(value)) {
                delegates.setWallpaperOverlay(value);
                return;
            }
            warnInvalidPreference('wallpaper_overlay', value);
        },
        solidBackground: (value: JsonValue | null | undefined): void => {
            if (value === null || value === undefined || isString(value)) {
                delegates.setSolidBackground(value === undefined ? null : value);
                return;
            }
            warnInvalidPreference('solid_background', value);
        },
        glassEnabled: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setGlassEnabled(value);
                return;
            }
            warnInvalidPreference('glass_enabled', value);
        },
        hiddenSidebarPages: (value: JsonValue | null | undefined): void => {
            if (isArray(value)) {
                delegates.setHiddenSidebarPages(normalizeStringArray(value, 200));
                return;
            }
            warnInvalidPreference('hidden_sidebar_pages', value);
        },
        showMainStatusIndicator: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setShowMainStatusIndicator(value);
                return;
            }
            warnInvalidPreference('show_main_status_indicator', value);
        },
        mainStatePreferenceVersion: (value: JsonValue | null | undefined): void => {
            if (isNumber(value) && Number.isFinite(value)) {
                state.cache.ui.mainStatePreferenceVersion = value;
                terminateHandledPromise(core.queuePersist('ui'));
                return;
            }
            warnInvalidPreference('main_state_preference_version', value);
        },
        hiddenDashboardElements: (value: JsonValue | null | undefined): void => {
            if (isArray(value)) {
                delegates.setHiddenDashboardElements(normalizeStringArray(value, 200));
                return;
            }
            warnInvalidPreference('hidden_dashboard_elements', value);
        },
        dashboardLocked: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setDashboardLocked(value);
                return;
            }
            warnInvalidPreference('dashboard_locked', value);
        },
        dashboardImageCard: (value: JsonValue | null | undefined): void => {
            if (value === null || value === undefined || isString(value)) {
                delegates.setDashboardImageCard(value === undefined ? null : value);
                return;
            }
            warnInvalidPreference('dashboard_image_card', value);
        },
        dashboardImageCardFit: (value: JsonValue | null | undefined): void => {
            if (isString(value) && isImageFitType(value)) {
                delegates.setDashboardImageCardFit(value);
                return;
            }
            warnInvalidPreference('dashboard_image_card_fit', value);
        },
        dashboardMemo: (value: JsonValue | null | undefined): void => {
            if (value === null || value === undefined || isString(value)) {
                delegates.setDashboardMemo(value === undefined ? null : value);
                return;
            }
            warnInvalidPreference('dashboard_memo', value);
        },
        defaultPage: (value: JsonValue | null | undefined): void => {
            if (value === null || value === undefined || isString(value)) {
                delegates.setDefaultPage(value === undefined ? null : value);
                return;
            }
            warnInvalidPreference('default_page', value);
        },
        chartColorMode: (value: JsonValue | null | undefined): void => {
            if (isString(value) && isChartColorModeType(value)) {
                delegates.setChartColorMode(value);
                return;
            }
            warnInvalidPreference('chart_color_mode', value);
        },
        chartStaticColor: (value: JsonValue | null | undefined): void => {
            if (isString(value) && value.trim()) {
                delegates.setChartStaticColor(value);
                return;
            }
            warnInvalidPreference('chart_static_color', value);
        },
        headerAutoHide: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setHeaderAutoHide(value);
                return;
            }
            warnInvalidPreference('header_auto_hide', value);
        },
        showScrollToTopButton: (value: JsonValue | null | undefined): void => {
            if (isBoolean(value)) {
                delegates.setShowScrollToTopButton(value);
                return;
            }
            warnInvalidPreference('show_scroll_to_top_button', value);
        },
        pageAnimation: (value: JsonValue | null | undefined): void => {
            if (isString(value)) {
                delegates.setPageAnimation(value);
                return;
            }
            warnInvalidPreference('page_animation', value);
        },
        modalAnimation: (value: JsonValue | null | undefined): void => {
            if (isString(value)) {
                delegates.setModalAnimation(value);
                return;
            }
            warnInvalidPreference('modal_animation', value);
        },
        notificationAnimation: (value: JsonValue | null | undefined): void => {
            if (isString(value)) {
                delegates.setNotificationAnimation(value);
                return;
            }
            warnInvalidPreference('notification_animation', value);
        },
        animationSpeed: (value: JsonValue | null | undefined): void => {
            if (isString(value)) {
                delegates.setAnimationSpeed(value);
                return;
            }
            warnInvalidPreference('animation_speed', value);
        },
        lastVirtualModelStrategy: (value: JsonValue | null | undefined): void => {
            if (value === 'load_balancing' || value === 'failover') {
                state.cache.ui.lastVirtualModelStrategy = value;
                terminateHandledPromise(core.queuePersist('ui'));
                return;
            }
            warnInvalidPreference('last_virtual_model_strategy', value);
        }
    };
};

export { createPreferenceHandlers };
