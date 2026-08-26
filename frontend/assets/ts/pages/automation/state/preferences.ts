/* SoAI - Automation page preferences [frontend/assets/ts/pages/automation/state/preferences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { isAutomationCalendarFirstDay, isAutomationCalendarRangeTitleFormat, isAutomationCalendarTimeFormat, isAutomationCalendarWeekNumbering, isAutomationViewMode } from '@core/automation/guards.ts';
import { isBoolean, isNumber, isString } from '@core/typeGuards.ts';
import type { AutomationCalendarSettings, AutomationPageState, AutomationPreferences } from '@pages/automation/types.ts';

const STORAGE_KEY = 'automation_preferences';

const AUTOMATION_SPLIT_MIN_PERCENT = 50;
const AUTOMATION_SPLIT_MAX_PERCENT = 80;

const DEFAULT_AUTOMATION_CALENDAR_SETTINGS: AutomationCalendarSettings = {
    firstDayOfWeek: 'auto',
    showWeekNumbers: false,
    weekNumbering: 'local',
    timeFormat: 'locale',
    rangeTitleFormat: 'locale',
    showRangeTitleWeekday: true
};

const DEFAULT_PREFERENCES: AutomationPreferences = { viewMode: 'month', splitLeftPercent: 80, calendarSettings: DEFAULT_AUTOMATION_CALENDAR_SETTINGS };

class AutomationPreferencesCorruptError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'AutomationPreferencesCorruptError';
    }
}

const requireField = <T extends JsonValue>(candidate: JsonObject, key: string, guard: (value: JsonValue) => value is T, label: string): T => {
    const value = candidate[key] ?? null;
    if (guard(value)) {
        return value;
    }
    throw new AutomationPreferencesCorruptError(`Automation preferences ${label} is invalid`);
};

const loadAutomationPreferences = (storage: StorageService): AutomationPreferences => {
    const candidate = storage.get(STORAGE_KEY, null);
    if (candidate === null) {
        return { ...DEFAULT_PREFERENCES };
    }
    if (!isJsonObject(candidate)) {
        throw new AutomationPreferencesCorruptError('Automation preferences payload must be an object');
    }

    const viewModeCandidate = requireField(candidate, 'viewMode', isString, 'viewMode');
    if (!isAutomationViewMode(viewModeCandidate)) {
        throw new AutomationPreferencesCorruptError('Automation preferences viewMode is invalid');
    }

    const splitCandidate = requireField(candidate, 'splitLeftPercent', isNumber, 'splitLeftPercent');
    if (!Number.isFinite(splitCandidate) || splitCandidate < AUTOMATION_SPLIT_MIN_PERCENT || splitCandidate > AUTOMATION_SPLIT_MAX_PERCENT) {
        throw new AutomationPreferencesCorruptError('Automation preferences splitLeftPercent is out of range');
    }

    const calendarCandidate = requireField(candidate, 'calendarSettings', isJsonObject, 'calendarSettings');
    const firstDayRaw = requireField(calendarCandidate, 'firstDayOfWeek', isString, 'calendarSettings.firstDayOfWeek');
    if (!isAutomationCalendarFirstDay(firstDayRaw)) {
        throw new AutomationPreferencesCorruptError('Automation preferences calendarSettings.firstDayOfWeek is invalid');
    }
    const showWeekNumbers = requireField(calendarCandidate, 'showWeekNumbers', isBoolean, 'calendarSettings.showWeekNumbers');
    const weekNumberingRaw = requireField(calendarCandidate, 'weekNumbering', isString, 'calendarSettings.weekNumbering');
    if (!isAutomationCalendarWeekNumbering(weekNumberingRaw)) {
        throw new AutomationPreferencesCorruptError('Automation preferences calendarSettings.weekNumbering is invalid');
    }
    const timeFormatRaw = requireField(calendarCandidate, 'timeFormat', isString, 'calendarSettings.timeFormat');
    if (!isAutomationCalendarTimeFormat(timeFormatRaw)) {
        throw new AutomationPreferencesCorruptError('Automation preferences calendarSettings.timeFormat is invalid');
    }
    const rangeTitleFormatRaw = requireField(calendarCandidate, 'rangeTitleFormat', isString, 'calendarSettings.rangeTitleFormat');
    if (!isAutomationCalendarRangeTitleFormat(rangeTitleFormatRaw)) {
        throw new AutomationPreferencesCorruptError('Automation preferences calendarSettings.rangeTitleFormat is invalid');
    }
    const showRangeTitleWeekday = requireField(calendarCandidate, 'showRangeTitleWeekday', isBoolean, 'calendarSettings.showRangeTitleWeekday');

    return {
        viewMode: viewModeCandidate,
        splitLeftPercent: splitCandidate,
        calendarSettings: {
            firstDayOfWeek: firstDayRaw,
            showWeekNumbers,
            weekNumbering: weekNumberingRaw,
            timeFormat: timeFormatRaw,
            rangeTitleFormat: rangeTitleFormatRaw,
            showRangeTitleWeekday
        }
    };
};

const assertSplitPercent = (value: number): number => {
    if (!Number.isFinite(value) || value < AUTOMATION_SPLIT_MIN_PERCENT || value > AUTOMATION_SPLIT_MAX_PERCENT) {
        throw new Error('Automation splitLeftPercent is out of range');
    }
    return value;
};

const saveAutomationPreferences = (storage: StorageService, preferences: AutomationPreferences): void => {
    storage.set(STORAGE_KEY, {
        viewMode: preferences.viewMode,
        splitLeftPercent: assertSplitPercent(preferences.splitLeftPercent),
        calendarSettings: {
            firstDayOfWeek: preferences.calendarSettings.firstDayOfWeek,
            showWeekNumbers: preferences.calendarSettings.showWeekNumbers,
            weekNumbering: preferences.calendarSettings.weekNumbering,
            timeFormat: preferences.calendarSettings.timeFormat,
            rangeTitleFormat: preferences.calendarSettings.rangeTitleFormat,
            showRangeTitleWeekday: preferences.calendarSettings.showRangeTitleWeekday
        }
    });
};

const resetAutomationPreferences = (storage: StorageService): void => {
    storage.remove(STORAGE_KEY);
};

const persistAutomationPagePreferences = (storage: StorageService, state: AutomationPageState, preferencesCorrupt: boolean): void => {
    if (preferencesCorrupt) {
        throw new Error('Cannot persist automation preferences while preferences are corrupt');
    }
    saveAutomationPreferences(storage, {
        viewMode: state.viewMode,
        splitLeftPercent: state.splitLeftPercent,
        calendarSettings: state.calendarSettings
    });
};

export { AutomationPreferencesCorruptError, DEFAULT_AUTOMATION_CALENDAR_SETTINGS, loadAutomationPreferences, persistAutomationPagePreferences, resetAutomationPreferences, saveAutomationPreferences };
export { AUTOMATION_SPLIT_MAX_PERCENT, AUTOMATION_SPLIT_MIN_PERCENT };
