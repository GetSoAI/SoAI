/* SoAI - Power page restart reminder [frontend/assets/ts/pages/power/controllers/powerRestartReminder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPowerActionId } from '@pages/power/actions.ts';
import type { PowerActionId } from '@features/power/public.ts';

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
