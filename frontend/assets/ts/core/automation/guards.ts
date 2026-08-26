/* SoAI - Shared automation validation [frontend/assets/ts/core/automation/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AUTOMATION_CALENDAR_FIRST_DAYS, AUTOMATION_CALENDAR_RANGE_TITLE_FORMATS, AUTOMATION_CALENDAR_TIME_FORMATS, AUTOMATION_CALENDAR_WEEK_NUMBERINGS, AUTOMATION_RECURRENCES, AUTOMATION_RUN_STATUSES, AUTOMATION_VIEW_MODES, AUTOMATION_ZONE_STATUSES, type AutomationCalendarFirstDay, type AutomationCalendarRangeTitleFormat, type AutomationCalendarTimeFormat, type AutomationCalendarWeekNumbering, type AutomationRecurrence, type AutomationRunStatus, type AutomationViewMode, type AutomationZoneStatus } from '@core/automation/protocols.ts';

const isValueIn = <T, TValue extends string>(value: T, values: readonly TValue[]): value is T & TValue => {
    if (typeof value !== 'string') {
        return false;
    }
    const normalizedValue: string = value;
    for (const candidate of values) {
        if (candidate === normalizedValue) {
            return true;
        }
    }
    return false;
};

const isAutomationViewMode = <T>(value: T): value is T & AutomationViewMode => isValueIn(value, AUTOMATION_VIEW_MODES);

const isAutomationCalendarFirstDay = <T>(value: T): value is T & AutomationCalendarFirstDay => isValueIn(value, AUTOMATION_CALENDAR_FIRST_DAYS);

const isAutomationCalendarWeekNumbering = <T>(value: T): value is T & AutomationCalendarWeekNumbering => isValueIn(value, AUTOMATION_CALENDAR_WEEK_NUMBERINGS);

const isAutomationCalendarTimeFormat = <T>(value: T): value is T & AutomationCalendarTimeFormat => isValueIn(value, AUTOMATION_CALENDAR_TIME_FORMATS);

const isAutomationCalendarRangeTitleFormat = <T>(value: T): value is T & AutomationCalendarRangeTitleFormat => isValueIn(value, AUTOMATION_CALENDAR_RANGE_TITLE_FORMATS);

const isAutomationRecurrence = <T>(value: T): value is T & AutomationRecurrence => isValueIn(value, AUTOMATION_RECURRENCES);

const isAutomationRunStatus = <T>(value: T): value is T & AutomationRunStatus => isValueIn(value, AUTOMATION_RUN_STATUSES);

const isAutomationZoneStatus = <T>(value: T): value is T & AutomationZoneStatus => isValueIn(value, AUTOMATION_ZONE_STATUSES);

export { isAutomationCalendarFirstDay, isAutomationCalendarRangeTitleFormat, isAutomationCalendarTimeFormat, isAutomationCalendarWeekNumbering, isAutomationRecurrence, isAutomationRunStatus, isAutomationViewMode, isAutomationZoneStatus };
