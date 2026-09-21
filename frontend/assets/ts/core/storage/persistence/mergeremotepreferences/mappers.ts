/* SoAI - Shared frontend storage persistence merge remote preferences mapping [frontend/assets/ts/core/storage/persistence/mergeremotepreferences/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAnimationSpeed, isAnimationType, isChartColorModeType, isClockFormatType, isDateFormatPreference, isImageFitType, isInterfaceScalePercent, isMeasurementUnitsPreference, isRegionalLocalePreference, isThemeType } from '@core/storage/guards.ts';
import { normalizeModalStatesRecord } from '@core/storage/modalState.ts';
import { normalizeNonBlankStringOrNull, normalizeStringArray } from '@core/storage/normalization.ts';
import type { UiPreferences } from '@core/storage/persistence/mergeremotepreferences/types.ts';
import { normalizeAccentColorPreference } from '@core/theme/accentColor.ts';
import { normalizeSurfaceColorPreference } from '@core/theme/surfaceColor.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isBoolean, isNumber, isObject, isString } from '@core/typeGuards.ts';

const applyUiPatch = (patch: JsonValue | undefined, target: UiPreferences): void => {
    if (!isObject(patch)) {
        return;
    }

    const theme = patch['theme'];
    if (isThemeType(theme)) {
        target.theme = theme;
    }

    const accentColor = patch['accent_color'];
    if (accentColor === null) {
        target.accentColor = null;
    } else {
        const normalizedAccent = normalizeAccentColorPreference(accentColor);
        if (normalizedAccent) {
            target.accentColor = normalizedAccent;
        }
    }

    const surfaceColor = patch['surface_color'];
    if (surfaceColor === null) {
        target.surfaceColor = null;
    } else {
        const normalizedSurface = normalizeSurfaceColorPreference(surfaceColor);
        if (normalizedSurface) {
            target.surfaceColor = normalizedSurface;
        }
    }

    const promptEnhancerModel = patch['prompt_enhancer_model'];
    if (promptEnhancerModel === null || promptEnhancerModel === undefined || isString(promptEnhancerModel)) {
        target.promptEnhancerModel = promptEnhancerModel ?? null;
    }

    const dashboardLayout = patch['dashboard_layout'];
    if (dashboardLayout !== undefined && isJsonObject(dashboardLayout)) {
        target.dashboardLayout = dashboardLayout;
    }

    const interfaceScale = patch['interface_scale'];
    if (isInterfaceScalePercent(interfaceScale)) {
        target.interfaceScale = interfaceScale;
    }

    const language = patch['language'];
    if (isString(language) && language.trim()) {
        target.language = language;
    }

    const clockFormat = patch['clock_format'];
    if (isClockFormatType(clockFormat)) {
        target.clockFormat = clockFormat;
    }

    const headerClockEnabled = patch['header_clock_enabled'];
    if (isBoolean(headerClockEnabled)) {
        target.headerClockEnabled = headerClockEnabled;
    }

    const clockSecondsEnabled = patch['clock_seconds_enabled'];
    if (isBoolean(clockSecondsEnabled)) {
        target.clockSecondsEnabled = clockSecondsEnabled;
    }

    const regionalLocale = patch['regional_locale'];
    if (isRegionalLocalePreference(regionalLocale)) {
        target.regionalLocale = regionalLocale;
    }

    const dateFormat = patch['date_format'];
    if (isDateFormatPreference(dateFormat)) {
        target.dateFormat = dateFormat;
    }

    const measurementUnits = patch['measurement_units'];
    if (isMeasurementUnitsPreference(measurementUnits)) {
        target.measurementUnits = measurementUnits;
    }

    const notificationDuration = patch['notification_duration'];
    if (isNumber(notificationDuration) && Number.isFinite(notificationDuration)) {
        target.notificationDuration = notificationDuration;
    }

    const codeRecognitionEnabled = patch['code_recognition_enabled'];
    if (isBoolean(codeRecognitionEnabled)) {
        target.codeRecognitionEnabled = codeRecognitionEnabled;
    }

    const reduceMotions = patch['reduce_motions'];
    if (isBoolean(reduceMotions)) {
        target.reduceMotions = reduceMotions;
    }

    const soundEffects = patch['sound_effects'];
    if (isBoolean(soundEffects)) {
        target.soundEffects = soundEffects;
    }

    const liveStatusOverlayEnabled = patch['live_status_overlay_enabled'];
    if (isBoolean(liveStatusOverlayEnabled)) {
        target.liveStatusOverlayEnabled = liveStatusOverlayEnabled;
    }

    const modalStatesValue = patch['modal_states'];
    const modalStates = normalizeModalStatesRecord(modalStatesValue);
    if (modalStates) {
        target.modalStates = modalStates;
    }

    const wallpaperOverlay = patch['wallpaper_overlay'];
    if (isNumber(wallpaperOverlay) && Number.isFinite(wallpaperOverlay)) {
        target.wallpaperOverlay = wallpaperOverlay;
    }

    const solidBackground = patch['solid_background'];
    if (solidBackground === null || solidBackground === undefined || isString(solidBackground)) {
        target.solidBackground = solidBackground ?? null;
    }

    const glassEnabled = patch['glass_enabled'];
    if (isBoolean(glassEnabled)) {
        target.glassEnabled = glassEnabled;
    }

    const hiddenSidebarPages = patch['hidden_sidebar_pages'];
    if (isArray(hiddenSidebarPages)) {
        target.hiddenSidebarPages = normalizeStringArray(hiddenSidebarPages, 200);
    }

    const showMainStatusIndicator = patch['show_main_status_indicator'];
    if (isBoolean(showMainStatusIndicator)) {
        target.showMainStatusIndicator = showMainStatusIndicator;
    }

    const mainStatePreferenceVersion = patch['main_state_preference_version'];
    if (isNumber(mainStatePreferenceVersion) && Number.isFinite(mainStatePreferenceVersion)) {
        target.mainStatePreferenceVersion = mainStatePreferenceVersion;
    }

    const hiddenDashboardElements = patch['hidden_dashboard_elements'];
    if (isArray(hiddenDashboardElements)) {
        target.hiddenDashboardElements = normalizeStringArray(hiddenDashboardElements, 200);
    }

    const dashboardLocked = patch['dashboard_locked'];
    if (isBoolean(dashboardLocked)) {
        target.dashboardLocked = dashboardLocked;
    }

    const dashboardImageCard = patch['dashboard_image_card'];
    if (dashboardImageCard === null || dashboardImageCard === undefined || isString(dashboardImageCard)) {
        target.dashboardImageCard = dashboardImageCard ?? null;
    }

    const dashboardImageCardFit = patch['dashboard_image_card_fit'];
    if (isImageFitType(dashboardImageCardFit)) {
        target.dashboardImageCardFit = dashboardImageCardFit;
    }

    const dashboardMemo = patch['dashboard_memo'];
    if (dashboardMemo === null || dashboardMemo === undefined || isString(dashboardMemo)) {
        target.dashboardMemo = normalizeNonBlankStringOrNull(dashboardMemo ?? null);
    }

    const defaultPage = patch['default_page'];
    if (defaultPage === null || defaultPage === undefined || isString(defaultPage)) {
        target.defaultPage = normalizeNonBlankStringOrNull(defaultPage ?? null);
    }

    const chartColorMode = patch['chart_color_mode'];
    if (isChartColorModeType(chartColorMode)) {
        target.chartColorMode = chartColorMode;
    }

    const chartStaticColor = patch['chart_static_color'];
    if (isString(chartStaticColor) && chartStaticColor.trim()) {
        target.chartStaticColor = chartStaticColor;
    }

    const headerAutoHide = patch['header_auto_hide'];
    if (isBoolean(headerAutoHide)) {
        target.headerAutoHide = headerAutoHide;
    }

    const showScrollToTopButton = patch['show_scroll_to_top_button'];
    if (isBoolean(showScrollToTopButton)) {
        target.showScrollToTopButton = showScrollToTopButton;
    }

    const pageAnimation = patch['page_animation'];
    if (isAnimationType(pageAnimation)) {
        target.pageAnimation = pageAnimation;
    }

    const modalAnimation = patch['modal_animation'];
    if (isAnimationType(modalAnimation)) {
        target.modalAnimation = modalAnimation;
    }

    const notificationAnimation = patch['notification_animation'];
    if (isAnimationType(notificationAnimation)) {
        target.notificationAnimation = notificationAnimation;
    }

    const animationSpeed = patch['animation_speed'];
    if (isAnimationSpeed(animationSpeed)) {
        target.animationSpeed = animationSpeed;
    }

    const lastVirtualModelStrategy = patch['last_virtual_model_strategy'];
    if (lastVirtualModelStrategy === 'load_balancing' || lastVirtualModelStrategy === 'failover') {
        target.lastVirtualModelStrategy = lastVirtualModelStrategy;
    }
};

export { applyUiPatch };
