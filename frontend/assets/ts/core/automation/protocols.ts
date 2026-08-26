/* SoAI - Shared automation protocols [frontend/assets/ts/core/automation/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const AUTOMATION_RUN_ACTIVITY_SERVICE_ID = 'features.automation.runActivity';

type AutomationViewMode = 'month' | 'week' | 'day';
type AutomationCalendarFirstDay = 'auto' | 'sunday' | 'monday';
type AutomationCalendarWeekNumbering = 'iso' | 'local';
type AutomationCalendarTimeFormat = 'locale' | '12h' | '24h';
type AutomationCalendarRangeTitleFormat = 'locale' | 'iso' | 'us' | 'eu';
type AutomationRecurrence = 'none' | 'hourly' | 'daily' | 'weekly' | 'monthly' | 'yearly';
type AutomationRunStatus = 'queued' | 'running' | 'completed' | 'error' | 'cancelled' | 'abandoned';
type AutomationZoneStatus = 'scheduled' | AutomationRunStatus;

const AUTOMATION_VIEW_MODES: readonly AutomationViewMode[] = ['month', 'week', 'day'];
const AUTOMATION_CALENDAR_FIRST_DAYS: readonly AutomationCalendarFirstDay[] = ['auto', 'sunday', 'monday'];
const AUTOMATION_CALENDAR_WEEK_NUMBERINGS: readonly AutomationCalendarWeekNumbering[] = ['iso', 'local'];
const AUTOMATION_CALENDAR_TIME_FORMATS: readonly AutomationCalendarTimeFormat[] = ['locale', '12h', '24h'];
const AUTOMATION_CALENDAR_RANGE_TITLE_FORMATS: readonly AutomationCalendarRangeTitleFormat[] = ['locale', 'iso', 'us', 'eu'];
const AUTOMATION_RECURRENCES: readonly AutomationRecurrence[] = ['none', 'hourly', 'daily', 'weekly', 'monthly', 'yearly'];
const AUTOMATION_RUN_STATUSES: readonly AutomationRunStatus[] = ['queued', 'running', 'completed', 'error', 'cancelled', 'abandoned'];
const AUTOMATION_ZONE_STATUSES: readonly AutomationZoneStatus[] = ['scheduled', 'queued', 'running', 'completed', 'error', 'cancelled', 'abandoned'];

interface AutomationRunActivitySnapshot {
    initialized: boolean;
    hasRunning: boolean;
    runningAutomationIds: ReadonlySet<string>;
}

type AutomationRunActivitySubscribeContract = {
    subscribe: (listener: (snapshot: AutomationRunActivitySnapshot) => void) => () => void;
};

type AutomationRunActivityLifecycleContract = {
    initialize: () => Promise<void>;
    destroy: () => Promise<void>;
};

export { AUTOMATION_CALENDAR_FIRST_DAYS, AUTOMATION_CALENDAR_RANGE_TITLE_FORMATS, AUTOMATION_CALENDAR_TIME_FORMATS, AUTOMATION_CALENDAR_WEEK_NUMBERINGS, AUTOMATION_RECURRENCES, AUTOMATION_RUN_ACTIVITY_SERVICE_ID, AUTOMATION_RUN_STATUSES, AUTOMATION_VIEW_MODES, AUTOMATION_ZONE_STATUSES };
export type { AutomationCalendarFirstDay, AutomationCalendarRangeTitleFormat, AutomationCalendarTimeFormat, AutomationCalendarWeekNumbering, AutomationRecurrence, AutomationRunActivityLifecycleContract, AutomationRunActivitySnapshot, AutomationRunActivitySubscribeContract, AutomationRunStatus, AutomationViewMode, AutomationZoneStatus };
