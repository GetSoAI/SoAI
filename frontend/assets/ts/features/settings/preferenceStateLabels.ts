/* SoAI - Settings feature preference state labels [frontend/assets/ts/features/settings/preferenceStateLabels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ToggleLabelState } from '@core/toggleSwitch.ts';

const resolvePreferenceStateLabel = (enabled: boolean): string => {
    return enabled ? i18n.t('settings.preferences.enabled') : i18n.t('settings.preferences.disabled');
};

const getPreferenceStateLabels = (): ToggleLabelState => {
    return {
        trueLabel: resolvePreferenceStateLabel(true),
        falseLabel: resolvePreferenceStateLabel(false)
    };
};

export { getPreferenceStateLabels, resolvePreferenceStateLabel };
