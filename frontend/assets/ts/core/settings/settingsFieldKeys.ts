/* SoAI - Settings field key ownership [frontend/assets/ts/core/settings/settingsFieldKeys.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type SettingsFieldKeyType = 'config' | 'ui' | 'manual';

type UiPreferenceKey = 'accentColor' | 'animationSpeed' | 'chartColorMode' | 'chartStaticColor' | 'clockFormat' | 'clockSecondsEnabled' | 'codeRecognitionEnabled' | 'dashboardLocked' | 'dateFormat' | 'defaultPage' | 'glassEnabled' | 'headerAutoHide' | 'headerClockEnabled' | 'interfaceScale' | 'language' | 'measurementUnits' | 'modalAnimation' | 'notificationAnimation' | 'notificationDuration' | 'pageAnimation' | 'promptEnhancerModel' | 'reduceMotions' | 'regionalLocale' | 'showMainStatusIndicator' | 'showScrollToTopButton' | 'solidBackground' | 'soundEffects' | 'surfaceColor' | 'liveStatusOverlayEnabled' | 'theme' | 'wallpaperOverlay';

interface ParsedSettingsFieldKey {
    fieldType: SettingsFieldKeyType;
    sourceKey: string;
    surfaceKey: string;
}

const SETTINGS_CONFIG_FIELD_PREFIX = 'config:';
const SETTINGS_UI_FIELD_PREFIX = 'ui:';
const SETTINGS_MANUAL_FIELD_PREFIX = 'manual:';

const createSettingsConfigFieldKey = (path: string): string => `${SETTINGS_CONFIG_FIELD_PREFIX}${path}`;

const createSettingsUiPreferenceFieldKey = (sourceKey: UiPreferenceKey, surfaceKey: string = sourceKey): string => `${SETTINGS_UI_FIELD_PREFIX}${sourceKey}:${surfaceKey}`;

const createSettingsManualFieldKey = (sourceKey: string): string => `${SETTINGS_MANUAL_FIELD_PREFIX}${sourceKey}`;

const parseSettingsFieldKey = (fieldKey: string): ParsedSettingsFieldKey | null => {
    if (fieldKey.startsWith(SETTINGS_CONFIG_FIELD_PREFIX)) {
        const sourceKey = fieldKey.slice(SETTINGS_CONFIG_FIELD_PREFIX.length);
        return sourceKey ? { fieldType: 'config', sourceKey, surfaceKey: sourceKey } : null;
    }
    if (fieldKey.startsWith(SETTINGS_UI_FIELD_PREFIX)) {
        const rest = fieldKey.slice(SETTINGS_UI_FIELD_PREFIX.length);
        const separatorIndex = rest.indexOf(':');
        if (separatorIndex <= 0) {
            return null;
        }
        const sourceKey = rest.slice(0, separatorIndex);
        const surfaceKey = rest.slice(separatorIndex + 1);
        return sourceKey && surfaceKey ? { fieldType: 'ui', sourceKey, surfaceKey } : null;
    }
    if (fieldKey.startsWith(SETTINGS_MANUAL_FIELD_PREFIX)) {
        const sourceKey = fieldKey.slice(SETTINGS_MANUAL_FIELD_PREFIX.length);
        return sourceKey ? { fieldType: 'manual', sourceKey, surfaceKey: sourceKey } : null;
    }
    return null;
};

export { createSettingsConfigFieldKey, createSettingsManualFieldKey, createSettingsUiPreferenceFieldKey, parseSettingsFieldKey };
export type { ParsedSettingsFieldKey, SettingsFieldKeyType, UiPreferenceKey };
