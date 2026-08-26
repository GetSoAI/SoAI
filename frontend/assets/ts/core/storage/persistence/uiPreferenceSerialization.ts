/* SoAI - Frontend UI preference persistence serialization [frontend/assets/ts/core/storage/persistence/uiPreferenceSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { UiPreferences } from '@core/storage/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeUiPreferences = (preferences: UiPreferences): JsonObject => ({
    theme: preferences.theme,
    'accent_color': preferences.accentColor,
    'surface_color': preferences.surfaceColor,
    'prompt_enhancer_model': preferences.promptEnhancerModel,
    'dashboard_layout': preferences.dashboardLayout,
    'interface_scale': preferences.interfaceScale,
    language: preferences.language,
    'clock_format': preferences.clockFormat,
    'header_clock_enabled': preferences.headerClockEnabled,
    'clock_seconds_enabled': preferences.clockSecondsEnabled,
    'regional_locale': preferences.regionalLocale,
    'date_format': preferences.dateFormat,
    'measurement_units': preferences.measurementUnits,
    'notification_duration': preferences.notificationDuration,
    'code_recognition_enabled': preferences.codeRecognitionEnabled,
    'reduce_motions': preferences.reduceMotions,
    'sound_effects': preferences.soundEffects,
    'live_status_overlay_enabled': preferences.liveStatusOverlayEnabled,
    'modal_states': preferences.modalStates,
    'wallpaper_overlay': preferences.wallpaperOverlay,
    'solid_background': preferences.solidBackground,
    'glass_enabled': preferences.glassEnabled,
    'hidden_sidebar_pages': preferences.hiddenSidebarPages,
    'show_main_status_indicator': preferences.showMainStatusIndicator,
    'main_state_preference_version': preferences.mainStatePreferenceVersion,
    'hidden_dashboard_elements': preferences.hiddenDashboardElements,
    'dashboard_locked': preferences.dashboardLocked,
    'dashboard_image_card': preferences.dashboardImageCard,
    'dashboard_image_card_fit': preferences.dashboardImageCardFit,
    'dashboard_memo': preferences.dashboardMemo,
    'chart_color_mode': preferences.chartColorMode,
    'chart_static_color': preferences.chartStaticColor,
    'header_auto_hide': preferences.headerAutoHide,
    'show_scroll_to_top_button': preferences.showScrollToTopButton,
    'page_animation': preferences.pageAnimation,
    'modal_animation': preferences.modalAnimation,
    'notification_animation': preferences.notificationAnimation,
    'animation_speed': preferences.animationSpeed,
    'last_virtual_model_strategy': preferences.lastVirtualModelStrategy
});

export { serializeUiPreferences };
