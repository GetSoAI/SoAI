/* SoAI - Default start time for newly created automations [frontend/assets/ts/pages/automation/controllers/AutomationCreateStartDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isSameDay, startOfDay, toStartLocal } from '@core/time/localCalendar.ts';

const CREATE_START_STEP_MINUTES = 15;
const FUTURE_DAY_START_HOUR = 9;

const resolveAutomationCreateStartLocal = (selectedDateUtcMs: number, nowMs: number): string => {
    const now = new Date(nowMs);
    const selectedDay = startOfDay(new Date(selectedDateUtcMs));
    if (!isSameDay(selectedDay, now)) {
        selectedDay.setHours(FUTURE_DAY_START_HOUR, 0, 0, 0);
        return toStartLocal(selectedDay);
    }
    const next = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), now.getMinutes(), 0, 0);
    next.setMinutes((Math.floor(next.getMinutes() / CREATE_START_STEP_MINUTES) + 1) * CREATE_START_STEP_MINUTES);
    return toStartLocal(next);
};

export { resolveAutomationCreateStartLocal };
