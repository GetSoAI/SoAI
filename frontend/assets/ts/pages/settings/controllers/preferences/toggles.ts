/* SoAI - Settings page toggles [frontend/assets/ts/pages/settings/controllers/preferences/toggles.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { getPreferenceStateLabels, UI_IDS } from '@features/settings/public.ts';
import type { PreferencesManagerHost } from '@pages/settings/controllers/preferences/types.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';

interface PreferenceToggleDefinition {
    id: string;
    uiPrefKey: UiPreferenceKey;
    itemClassName?: string | undefined;
    getValue: () => boolean;
    setValue: (value: boolean) => void;
    isDisabled: () => boolean;
    getLabel: () => string;
    getHelp: () => string;
}

const SETTINGS_CLOCK_PREFERENCE_CLASS = 'settings-clock-preference';

const createPreferenceToggleDefinitions = (host: PreferencesManagerHost): PreferenceToggleDefinition[] => {
    return [
        {
            id: UI_IDS.HEADER_CLOCK_TOGGLE,
            uiPrefKey: 'headerClockEnabled',
            itemClassName: SETTINGS_CLOCK_PREFERENCE_CLASS,
            getValue: () => host.getUiPrefValue('headerClockEnabled') !== false,
            setValue: (value: boolean): void => {
                host.setUiPrefValue('headerClockEnabled', value);
                if (!value) {
                    host.setUiPrefValue('clockSecondsEnabled', false);
                }
            },
            isDisabled: (): boolean => false,
            getLabel: () => i18n.t('settings.preferences.headerClock.label'),
            getHelp: () => i18n.t('settings.preferences.headerClock.help')
        },
        {
            id: UI_IDS.CLOCK_SECONDS_TOGGLE,
            uiPrefKey: 'clockSecondsEnabled',
            itemClassName: SETTINGS_CLOCK_PREFERENCE_CLASS,
            getValue: () => host.getUiPrefValue('headerClockEnabled') !== false && host.getUiPrefValue('clockSecondsEnabled') === true,
            setValue: (value: boolean): void => {
                host.setUiPrefValue('clockSecondsEnabled', host.getUiPrefValue('headerClockEnabled') !== false && value);
            },
            isDisabled: () => host.getUiPrefValue('headerClockEnabled') === false,
            getLabel: () => i18n.t('settings.preferences.clockSeconds.label'),
            getHelp: () => i18n.t('settings.preferences.clockSeconds.help')
        },
        {
            id: 'sound-effects-toggle',
            uiPrefKey: 'soundEffects',
            getValue: () => host.getUiPrefValue('soundEffects') === true,
            setValue: (value: boolean): void => {
                host.setUiPrefValue('soundEffects', value);
            },
            isDisabled: (): boolean => false,
            getLabel: () => i18n.t('settings.preferences.sound.effects.label'),
            getHelp: () => i18n.t('settings.preferences.sound.effects.help')
        },
        {
            id: 'live-status-overlay-toggle',
            uiPrefKey: 'liveStatusOverlayEnabled',
            getValue: () => host.getUiPrefValue('liveStatusOverlayEnabled') === true,
            setValue: (value: boolean): void => {
                host.setUiPrefValue('liveStatusOverlayEnabled', value);
            },
            isDisabled: (): boolean => false,
            getLabel: () => i18n.t('settings.preferences.liveStatusOverlay.label'),
            getHelp: () => i18n.t('settings.preferences.liveStatusOverlay.help')
        }
    ];
};

export { createPreferenceToggleDefinitions, getPreferenceStateLabels };
export type { PreferenceToggleDefinition };
