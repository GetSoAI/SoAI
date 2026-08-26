/* SoAI - Automation page contracts [frontend/assets/ts/pages/automation/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationCalendarFirstDay, AutomationCalendarRangeTitleFormat, AutomationCalendarTimeFormat, AutomationCalendarWeekNumbering, AutomationRecurrence, AutomationRunStatus, AutomationViewMode, AutomationZoneStatus } from '@core/automation/protocols.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { AutomationDataService, AutomationDefinition, AutomationZone } from '@features/automation/public.ts';

interface AutomationCalendarSettings {
    firstDayOfWeek: AutomationCalendarFirstDay;
    showWeekNumbers: boolean;
    weekNumbering: AutomationCalendarWeekNumbering;
    timeFormat: AutomationCalendarTimeFormat;
    rangeTitleFormat: AutomationCalendarRangeTitleFormat;
    showRangeTitleWeekday: boolean;
}

interface AutomationInitialSelection {
    focusDateUtcMs: number;
    selectedDateUtcMs: number;
    selectedZoneKey: string;
}

interface AutomationUiRefs {
    root: HTMLElement;
    contentWrapper: HTMLElement;
    preferencesCorruptOverlay: HTMLElement;
    rangeTitle: HTMLElement;
    todayButton: HTMLButtonElement;
    calendarRoot: HTMLElement;
    registryRoot: HTMLElement;
    registryScroll: HTMLElement;
    automationsRoot: HTMLElement;
    windowRunsRoot: HTMLElement;
    splitter: HTMLElement;
    viewToggle: HTMLElement;
    registryOverlayToggle: HTMLButtonElement;
}

interface AutomationPreferences {
    viewMode: AutomationViewMode;
    splitLeftPercent: number;
    calendarSettings: AutomationCalendarSettings;
}

interface AutomationPageState {
    viewMode: AutomationViewMode;
    registryOverlayOpen: boolean;
    calendarSettings: AutomationCalendarSettings;
    focusDateUtcMs: number;
    selectedDateUtcMs: number;
    selectedZoneKey: string | null;
    splitLeftPercent: number;
    automations: readonly AutomationDefinition[];
    automationRegistryLimit: number;
    automationRegistryOffset: number;
    automationRegistryHasMore: boolean;
    zones: readonly AutomationZone[];
}

interface AutomationPageServices {
    dataService: AutomationDataService;
    storage: StorageService;
}

export type { AutomationCalendarFirstDay, AutomationCalendarRangeTitleFormat, AutomationCalendarSettings, AutomationCalendarTimeFormat, AutomationCalendarWeekNumbering, AutomationInitialSelection, AutomationPageServices, AutomationPageState, AutomationPreferences, AutomationRecurrence, AutomationRunStatus, AutomationUiRefs, AutomationViewMode, AutomationZoneStatus };
