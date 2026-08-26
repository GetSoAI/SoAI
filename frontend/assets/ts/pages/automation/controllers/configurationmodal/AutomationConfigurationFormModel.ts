/* SoAI - Automation page configuration form model [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationConfigurationFormModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAutomationRecurrence } from '@core/automation/guards.ts';
import { AUTOMATION_RECURRENCES } from '@core/automation/protocols.ts';
import { normalizeColor } from '@core/ui/colorToolkitBase.ts';
import type { AutomationColor } from '@features/automation/public.ts';
import type { AutomationRecurrence } from '@pages/automation/types.ts';

interface AutomationConfigurationLimits {
    maxRunMinutes: number;
}

const HARD_MAX_TURNS = 1000;
const HARD_MAX_TURN_CHARS = 100000;
const HARD_MAX_RUN_MINUTES = 1440;
const AUTOMATION_RECURRENCE_VALUES: readonly AutomationRecurrence[] = AUTOMATION_RECURRENCES;

const DEFAULT_AUTOMATION_CONFIGURATION_LIMITS: AutomationConfigurationLimits = {
    maxRunMinutes: 30
};

const resolveAutomationRecurrence = (value: string): AutomationRecurrence | null => {
    return isAutomationRecurrence(value) ? value : null;
};

const normalizeAutomationColorSelection = (value: string): AutomationColor => {
    const normalized = normalizeColor(value);
    if (normalized === null || normalized === 'Red' || normalized === 'Yellow' || normalized === 'Purple' || normalized === 'Green' || normalized === 'Blue') {
        return normalized;
    }
    throw new Error('Automation color selection is invalid');
};

export { AUTOMATION_RECURRENCE_VALUES, DEFAULT_AUTOMATION_CONFIGURATION_LIMITS, HARD_MAX_RUN_MINUTES, HARD_MAX_TURN_CHARS, HARD_MAX_TURNS, normalizeAutomationColorSelection, resolveAutomationRecurrence };
export type { AutomationConfigurationLimits };
