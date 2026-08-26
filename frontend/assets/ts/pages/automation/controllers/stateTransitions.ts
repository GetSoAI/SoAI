/* SoAI - Automation page state transitions [frontend/assets/ts/pages/automation/controllers/stateTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { addDays, requireIsoDateToUtcMs, startOfDay } from '@core/time/localCalendar.ts';
import { resolveAutomationZoneByKey } from '@pages/automation/contracts/zoneKey.ts';
import { resolveAutomationWindow } from '@pages/automation/controllers/automationWindow.ts';
import type { AutomationPageState, AutomationViewMode } from '@pages/automation/types.ts';

const navigateCalendar = (state: AutomationPageState, direction: number): AutomationPageState => {
    const focus = new Date(state.focusDateUtcMs);
    if (state.viewMode === 'month') {
        const next = new Date(focus.getFullYear(), focus.getMonth() + direction, 1, 0, 0, 0, 0);
        const start = startOfDay(next).getTime();
        return { ...state, focusDateUtcMs: start, selectedDateUtcMs: start };
    }
    if (state.viewMode === 'week') {
        const start = startOfDay(addDays(focus, 7 * direction)).getTime();
        return { ...state, focusDateUtcMs: start, selectedDateUtcMs: start };
    }
    const selected = new Date(state.selectedDateUtcMs);
    const start = startOfDay(addDays(selected, direction)).getTime();
    return { ...state, focusDateUtcMs: start, selectedDateUtcMs: start };
};

const applyViewMode = (state: AutomationPageState, viewMode: AutomationViewMode): AutomationPageState => {
    const seed = viewMode === 'month' ? new Date(state.focusDateUtcMs) : new Date(state.selectedDateUtcMs);
    const start = startOfDay(seed).getTime();
    return { ...state, viewMode, focusDateUtcMs: start, selectedDateUtcMs: start };
};

const selectDayAndZoom = (state: AutomationPageState, iso: string): AutomationPageState => {
    const startUtcMs = requireIsoDateToUtcMs(iso, 'Automation calendar day selection');
    return { ...state, viewMode: 'day', focusDateUtcMs: startUtcMs, selectedDateUtcMs: startUtcMs };
};

const applyZoneSelection = (state: AutomationPageState, key: string | null): { state: AutomationPageState; requiresWindowRefresh: boolean } => {
    if (!key) {
        return { state: { ...state, selectedZoneKey: null }, requiresWindowRefresh: false };
    }
    const found = resolveAutomationZoneByKey(state.zones, key);
    if (!found) {
        return { state: { ...state, selectedZoneKey: key }, requiresWindowRefresh: false };
    }

    const zoneDayUtcMs = startOfDay(new Date(found.scheduledAtMs)).getTime();
    let nextFocusUtcMs = state.focusDateUtcMs;
    if (state.viewMode === 'day' || state.viewMode === 'week') {
        nextFocusUtcMs = zoneDayUtcMs;
    } else {
        const focus = new Date(state.focusDateUtcMs);
        const zoneDate = new Date(zoneDayUtcMs);
        const differsMonth = focus.getFullYear() !== zoneDate.getFullYear() || focus.getMonth() !== zoneDate.getMonth();
        if (differsMonth) {
            nextFocusUtcMs = zoneDayUtcMs;
        }
    }

    const nextState: AutomationPageState = { ...state, selectedZoneKey: key, selectedDateUtcMs: zoneDayUtcMs, focusDateUtcMs: nextFocusUtcMs };
    const prevWindow = resolveAutomationWindow(state);
    const nextWindow = resolveAutomationWindow(nextState);
    const requiresWindowRefresh = prevWindow.fromUtcMs !== nextWindow.fromUtcMs || prevWindow.toUtcMs !== nextWindow.toUtcMs;
    return { state: nextState, requiresWindowRefresh };
};

export { applyViewMode, applyZoneSelection, navigateCalendar, selectDayAndZoom };
