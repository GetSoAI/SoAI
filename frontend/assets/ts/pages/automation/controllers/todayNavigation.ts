/* SoAI - Automation page today navigation [frontend/assets/ts/pages/automation/controllers/todayNavigation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isSameDay, startOfDay } from '@core/time/localCalendar.ts';
import { resolveAutomationWindow } from '@pages/automation/controllers/automationWindow.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

interface TodayNavigationResult {
    nextState: AutomationPageState;
    stateChanged: boolean;
    persistPreferences: boolean;
    requiresRefresh: boolean;
    centerNowLine: boolean;
    shouldCloseOccurrence: boolean;
}

const isCurrentMonthFocus = (state: AutomationPageState, now: Date): boolean => {
    const focus = new Date(state.focusDateUtcMs);
    return focus.getFullYear() === now.getFullYear() && focus.getMonth() === now.getMonth();
};

const isCurrentWeekFocus = (state: AutomationPageState, now: Date): boolean => {
    const window = resolveAutomationWindow(state);
    if (window.viewMode !== 'week') {
        throw new Error('Expected week window for today navigation');
    }
    for (const day of window.weekDays) {
        if (isSameDay(day, now)) {
            return true;
        }
    }
    return false;
};

const resolveNavigateTodayState = (state: AutomationPageState, todayStartUtcMs: number, now: Date): { nextState: AutomationPageState; persistPreferences: boolean; centerNowLine: boolean } => {
    const selectedIsToday = isSameDay(new Date(state.selectedDateUtcMs), now);
    const base: Pick<AutomationPageState, 'focusDateUtcMs' | 'selectedDateUtcMs' | 'selectedZoneKey'> = { focusDateUtcMs: todayStartUtcMs, selectedDateUtcMs: todayStartUtcMs, selectedZoneKey: null };

    if (state.viewMode === 'month') {
        if (!isCurrentMonthFocus(state, now)) {
            return { nextState: { ...state, ...base }, persistPreferences: false, centerNowLine: false };
        }
        if (!selectedIsToday) {
            return { nextState: { ...state, selectedDateUtcMs: todayStartUtcMs, selectedZoneKey: null }, persistPreferences: false, centerNowLine: false };
        }
        return { nextState: { ...state, ...base, viewMode: 'week' }, persistPreferences: true, centerNowLine: false };
    }

    if (state.viewMode === 'week') {
        if (!isCurrentWeekFocus(state, now)) {
            return { nextState: { ...state, ...base }, persistPreferences: false, centerNowLine: false };
        }
        if (!selectedIsToday) {
            return { nextState: { ...state, selectedDateUtcMs: todayStartUtcMs, selectedZoneKey: null }, persistPreferences: false, centerNowLine: false };
        }
        return { nextState: { ...state, ...base, viewMode: 'day' }, persistPreferences: true, centerNowLine: true };
    }

    if (selectedIsToday && state.selectedZoneKey === null) {
        return { nextState: state, persistPreferences: false, centerNowLine: true };
    }
    return { nextState: { ...state, ...base, viewMode: 'day' }, persistPreferences: state.viewMode !== 'day', centerNowLine: true };
};

const navigateToday = (state: AutomationPageState, now: Date = new Date()): TodayNavigationResult => {
    const todayStartUtcMs = startOfDay(now).getTime();
    const prevWindow = resolveAutomationWindow(state);
    const resolved = resolveNavigateTodayState(state, todayStartUtcMs, now);
    const nextState = resolved.nextState;
    const stateChanged = nextState !== state;
    const nextWindow = stateChanged ? resolveAutomationWindow(nextState) : prevWindow;
    const requiresRefresh = prevWindow.fromUtcMs !== nextWindow.fromUtcMs || prevWindow.toUtcMs !== nextWindow.toUtcMs;
    const shouldCloseOccurrence = state.selectedZoneKey !== null && nextState.selectedZoneKey === null;
    return {
        nextState,
        stateChanged,
        persistPreferences: resolved.persistPreferences,
        requiresRefresh,
        centerNowLine: resolved.centerNowLine,
        shouldCloseOccurrence
    };
};

export { navigateToday };
export type { TodayNavigationResult };
