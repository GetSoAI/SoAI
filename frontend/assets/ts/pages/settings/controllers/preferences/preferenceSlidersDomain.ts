/* SoAI - Settings General preference slider definitions [frontend/assets/ts/pages/settings/controllers/preferences/preferenceSlidersDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { INTERFACE_SCALE_MAX_PERCENT, INTERFACE_SCALE_MIN_PERCENT, INTERFACE_SCALE_STEP_PERCENT, isInterfaceScalePercent } from '@core/layout/interfaceScale.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { normalizeNotificationDuration } from '@pages/settings/controllers/preferences/service.ts';
import type { PreferencesManagerHost } from '@pages/settings/controllers/preferences/types.ts';
import { requireUiPrefsInterfaceScale, requireUiPrefsNotificationDuration } from '@pages/settings/controllers/uiprefs/guards.ts';

interface PreferenceSliderDefinition {
    id: string;
    valueId: string;
    uiPrefKey: UiPreferenceKey;
    min: number;
    max: number;
    step: number;
    getValue: () => number;
    setValue: (value: number) => void;
    formatValue: (value: number) => string;
    getLabel: () => string;
    getHelp: () => string;
}

const createPreferenceSliderDefinitions = (host: PreferencesManagerHost): PreferenceSliderDefinition[] => [
    {
        id: UI_IDS.NOTIFICATION_DURATION_SLIDER,
        valueId: UI_IDS.NOTIFICATION_DURATION_VALUE,
        uiPrefKey: 'notificationDuration',
        min: 1,
        max: 10,
        step: 1,
        getValue: () => normalizeNotificationDuration(requireUiPrefsNotificationDuration(host.getUiPrefValue('notificationDuration'))),
        setValue: (value: number): void => {
            host.setUiPrefValue('notificationDuration', normalizeNotificationDuration(value));
        },
        formatValue: (value: number) => i18n.t('settings.preferences.notificationDuration.value', { seconds: value }),
        getLabel: () => i18n.t('settings.preferences.notificationDuration.label'),
        getHelp: () => i18n.t('settings.preferences.notificationDuration.help')
    },
    {
        id: UI_IDS.INTERFACE_SCALE_SLIDER,
        valueId: UI_IDS.INTERFACE_SCALE_VALUE,
        uiPrefKey: 'interfaceScale',
        min: INTERFACE_SCALE_MIN_PERCENT,
        max: INTERFACE_SCALE_MAX_PERCENT,
        step: INTERFACE_SCALE_STEP_PERCENT,
        getValue: () => requireUiPrefsInterfaceScale(host.getUiPrefValue('interfaceScale')),
        setValue: (value: number): void => {
            if (isInterfaceScalePercent(value)) {
                host.setUiPrefValue('interfaceScale', value);
            }
        },
        formatValue: (value: number) => i18n.t('settings.preferences.interfaceScale.value', { percent: value }),
        getLabel: () => i18n.t('settings.preferences.interfaceScale.label'),
        getHelp: () => i18n.t('settings.preferences.interfaceScale.help')
    }
];

export { createPreferenceSliderDefinitions };
export type { PreferenceSliderDefinition };
