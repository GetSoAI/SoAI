/* SoAI - Automation page state [frontend/assets/ts/pages/automation/controllers/automationPageState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { startOfDay } from '@core/time/localCalendar.ts';
import { DEFAULT_AUTOMATION_CALENDAR_SETTINGS } from '@pages/automation/state/preferences.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

const createInitialAutomationPageState = (): AutomationPageState => {
    const now = startOfDay(new Date());
    return {
        viewMode: 'month',
        registryOverlayOpen: false,
        calendarSettings: { ...DEFAULT_AUTOMATION_CALENDAR_SETTINGS },
        focusDateUtcMs: now.getTime(),
        selectedDateUtcMs: now.getTime(),
        selectedZoneKey: null,
        splitLeftPercent: 80,
        automations: [],
        automationRegistryLimit: 100,
        automationRegistryOffset: 0,
        automationRegistryHasMore: false,
        zones: []
    };
};

const resetAutomationPagePreferenceState = (state: AutomationPageState): AutomationPageState => {
    const initialState = createInitialAutomationPageState();
    return {
        ...state,
        viewMode: initialState.viewMode,
        registryOverlayOpen: initialState.registryOverlayOpen,
        calendarSettings: { ...initialState.calendarSettings },
        splitLeftPercent: initialState.splitLeftPercent
    };
};

export { createInitialAutomationPageState, resetAutomationPagePreferenceState };
