/* SoAI - Power restart reminder policy [frontend/assets/ts/features/power/restartReminder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPowerActionId } from '@features/power/actionDefinitions.ts';
import type { PowerActionId } from '@features/power/actions.ts';

const CLEAR_RESTART_REMINDER_ACTIONS: ReadonlySet<PowerActionId> = new Set(['restartApplication', 'shutdownApplication', 'shutdownSystem', 'rebootSystem']);

const shouldClearRestartReminder = (actionKey: string): boolean => {
    const normalized = actionKey.trim();
    if (!normalized) {
        return false;
    }
    if (!isPowerActionId(normalized)) {
        return false;
    }
    return CLEAR_RESTART_REMINDER_ACTIONS.has(normalized);
};

export { shouldClearRestartReminder };
