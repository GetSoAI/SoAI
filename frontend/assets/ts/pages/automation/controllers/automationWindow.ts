/* SoAI - Automation page window [frontend/assets/ts/pages/automation/controllers/automationWindow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { addDays, buildMonthGrid, buildWeekDays, resolveWeekStartsOnSunday, startOfDay } from '@core/time/localCalendar.ts';
import type { AutomationCalendarFirstDay, AutomationViewMode } from '@pages/automation/types.ts';
import { resolveAutomationLocalizationLocale } from '@pages/automation/widgets/calendar/locale.ts';

interface WindowBase {
    fromUtcMs: number;
    toUtcMs: number;
    focusDate: Date;
    selectedDate: Date;
    weekStartsOnSunday: boolean;
}

interface BufferedAutomationWindow {
    periods: readonly BufferedAutomationWindowEntry[];
    fromUtcMs: number;
    toUtcMs: number;
    signature: string;
}

interface BufferedAutomationWindowEntry {
    offset: number;
    signature: string;
    window: AutomationWindow;
}

type MonthWindow = WindowBase & { viewMode: 'month'; monthGrid: Date[] };
type WeekWindow = WindowBase & { viewMode: 'week'; weekDays: Date[] };
type DayWindow = WindowBase & { viewMode: 'day'; day: Date };
type AutomationWindow = MonthWindow | WeekWindow | DayWindow;
type AutomationWindowState = { viewMode: AutomationViewMode; focusDateUtcMs: number; selectedDateUtcMs: number; calendarSettings: { firstDayOfWeek: AutomationCalendarFirstDay } };
type AutomationBufferedPeriodOffset = -1 | 0 | 1;

const AUTOMATION_BUFFERED_PERIOD_OFFSETS: readonly AutomationBufferedPeriodOffset[] = [-1, 0, 1];

const resolveWeekStartsOnSundayForCalendar = (locale: string, firstDay: AutomationCalendarFirstDay): boolean => {
    if (firstDay === 'sunday') {
        return true;
    }
    if (firstDay === 'monday') {
        return false;
    }
    return resolveWeekStartsOnSunday(locale);
};

const shiftFocusDateForView = (viewMode: AutomationViewMode, focusDateUtcMs: number, offset: number): number => {
    const focusDate = startOfDay(new Date(focusDateUtcMs));
    if (viewMode === 'month') {
        return new Date(focusDate.getFullYear(), focusDate.getMonth() + offset, 1, 0, 0, 0, 0).getTime();
    }
    if (viewMode === 'week') {
        return startOfDay(addDays(focusDate, offset * 7)).getTime();
    }
    return startOfDay(addDays(focusDate, offset)).getTime();
};

const buildWindowSignature = (window: AutomationWindow): string => `${window.viewMode}:${String(window.fromUtcMs)}:${String(window.toUtcMs)}`;

const resolveAutomationWindow = (state: AutomationWindowState, localizationLocale: string = resolveAutomationLocalizationLocale()): AutomationWindow => {
    const focusDate = startOfDay(new Date(state.focusDateUtcMs));
    const selectedDate = startOfDay(new Date(state.selectedDateUtcMs));
    const weekStartsOnSunday = resolveWeekStartsOnSundayForCalendar(localizationLocale, state.calendarSettings.firstDayOfWeek);

    if (state.viewMode === 'month') {
        const monthGrid = buildMonthGrid(focusDate, weekStartsOnSunday);
        const monthStart = monthGrid[0];
        const monthEnd = monthGrid[monthGrid.length - 1];
        if (!monthStart || !monthEnd) {
            throw new Error('Month grid must provide start and end dates');
        }
        return {
            viewMode: 'month',
            focusDate,
            selectedDate,
            weekStartsOnSunday,
            monthGrid,
            fromUtcMs: startOfDay(monthStart).getTime(),
            toUtcMs: startOfDay(addDays(monthEnd, 1)).getTime()
        };
    }
    if (state.viewMode === 'week') {
        const weekDays = buildWeekDays(focusDate, weekStartsOnSunday);
        const weekStart = weekDays[0];
        const weekEnd = weekDays[weekDays.length - 1];
        if (!weekStart || !weekEnd) {
            throw new Error('Week days must provide start and end dates');
        }
        return {
            viewMode: 'week',
            focusDate,
            selectedDate,
            weekStartsOnSunday,
            weekDays,
            fromUtcMs: startOfDay(weekStart).getTime(),
            toUtcMs: startOfDay(addDays(weekEnd, 1)).getTime()
        };
    }
    return {
        viewMode: 'day',
        focusDate,
        selectedDate,
        weekStartsOnSunday,
        day: selectedDate,
        fromUtcMs: selectedDate.getTime(),
        toUtcMs: startOfDay(addDays(selectedDate, 1)).getTime()
    };
};

const resolveBufferedAutomationWindow = (state: AutomationWindowState, localizationLocale: string = resolveAutomationLocalizationLocale()): BufferedAutomationWindow => {
    const periods = AUTOMATION_BUFFERED_PERIOD_OFFSETS.map((offset) => {
        const focusDateUtcMs = shiftFocusDateForView(state.viewMode, state.focusDateUtcMs, offset);
        const window = resolveAutomationWindow({ ...state, focusDateUtcMs, selectedDateUtcMs: offset === 0 ? state.selectedDateUtcMs : focusDateUtcMs }, localizationLocale);
        return { offset, window, signature: buildWindowSignature(window) };
    });
    const first = periods[0];
    const last = periods[periods.length - 1];
    if (!first || !last) {
        throw new Error('Buffered automation window must not be empty');
    }
    return {
        periods,
        fromUtcMs: first.window.fromUtcMs,
        toUtcMs: last.window.toUtcMs,
        signature: periods.map((entry) => `${String(entry.offset)}:${entry.signature}`).join('|')
    };
};

const buildAutomationWindowSignature = (state: AutomationWindowState, localizationLocale?: string): string => buildWindowSignature(resolveAutomationWindow(state, localizationLocale));

const buildAutomationBufferedWindowSignature = (state: AutomationWindowState, localizationLocale?: string): string => resolveBufferedAutomationWindow(state, localizationLocale).signature;

export { AUTOMATION_BUFFERED_PERIOD_OFFSETS, buildAutomationBufferedWindowSignature, buildAutomationWindowSignature, resolveAutomationWindow, resolveBufferedAutomationWindow, shiftFocusDateForView };
export type { AutomationWindow, AutomationWindowState, BufferedAutomationWindow, BufferedAutomationWindowEntry, MonthWindow, WeekWindow, DayWindow };
