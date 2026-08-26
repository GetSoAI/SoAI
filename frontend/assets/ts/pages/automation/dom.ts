/* SoAI - Automation page DOM contracts [frontend/assets/ts/pages/automation/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton, optionalHTMLElement, resolve } from '@core/dom/dom.ts';
import { resolveButtonList, resolveHTMLElementList, resolveInputList, resolveTextareaList } from '@core/dom/typedElementResolver.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import type { AutomationUiRefs } from '@pages/automation/types.ts';

interface AutomationDomHost {
    requireHTMLElement: (selector: string, context?: Element | undefined) => HTMLElement;
    optionalHTMLElement: (selector: string, context?: Element | undefined) => HTMLElement | null;
}

const requireActionButton = (modal: Element, action: string): HTMLButtonElement => {
    const selector = `button[data-action="${action}"]`;
    const element = resolve(selector, modal);
    if (element instanceof HTMLButtonElement) {
        return element;
    }
    throw new Error(`Automation modal action button missing: ${action}`);
};

const optionalAutomationCalendarScroll = (calendarRoot: HTMLElement): HTMLElement | null => {
    const selector = '[data-automation-scroll="calendar"]';
    return optionalHTMLElement(resolve(selector, calendarRoot), selector);
};

const optionalAutomationCalendarLoading = (calendarRoot: HTMLElement): HTMLElement | null => {
    const selector = '.automation-calendar-loading';
    return optionalHTMLElement(resolve(selector, calendarRoot), selector);
};

const requireAutomationCalendarStage = (calendarRoot: HTMLElement): HTMLElement => {
    const selector = '[data-automation-calendar-stage="true"]';
    const element = resolve(selector, calendarRoot);
    if (element instanceof HTMLElement) {
        return element;
    }
    throw new Error('Automation calendar stage missing');
};

const optionalAutomationCalendarStage = (calendarRoot: HTMLElement): HTMLElement | null => {
    const selector = '[data-automation-calendar-stage="true"]';
    return optionalHTMLElement(resolve(selector, calendarRoot), selector);
};

const requireAutomationCalendarScroll = (calendarRoot: HTMLElement): HTMLElement => {
    const element = optionalAutomationCalendarScroll(calendarRoot);
    if (element) {
        return element;
    }
    throw new Error('Automation calendar scroll container missing');
};

const optionalAutomationCalendarTrack = (calendarRoot: HTMLElement): HTMLElement | null => {
    const selector = '[data-automation-calendar-track="true"]';
    return optionalHTMLElement(resolve(selector, calendarRoot), selector);
};

const requireAutomationCalendarTrack = (calendarRoot: HTMLElement): HTMLElement => {
    const element = optionalAutomationCalendarTrack(calendarRoot);
    if (element) {
        return element;
    }
    throw new Error('Automation calendar track missing');
};

const queryAutomationCalendarPeriods = (calendarRoot: HTMLElement): HTMLElement[] => {
    return resolveHTMLElementList('[data-automation-period-offset]', calendarRoot, 'Automation calendar period');
};

const optionalAutomationMonthDay = (calendarRoot: HTMLElement): HTMLElement | null => {
    const selector = '.automation-month-day';
    return optionalHTMLElement(resolve(selector, calendarRoot), selector);
};

const optionalAutomationMonthDayHeader = (day: HTMLElement): HTMLElement | null => {
    const selector = '.automation-month-day-header';
    return optionalHTMLElement(resolve(selector, day), selector);
};

const optionalAutomationMonthZones = (day: HTMLElement): HTMLElement | null => {
    const selector = '.automation-month-zones';
    return optionalHTMLElement(resolve(selector, day), selector);
};

const optionalAutomationZoneChip = (calendarRoot: HTMLElement): HTMLElement | null => {
    const selector = '.automation-zone-chip';
    return optionalHTMLElement(resolve(selector, calendarRoot), selector);
};

const queryAutomationNowLines = (root: HTMLElement): HTMLElement[] => {
    return resolveHTMLElementList('.automation-now-line', root, 'Automation now line');
};

const queryAutomationNowTags = (root: HTMLElement): HTMLElement[] => {
    return resolveHTMLElementList('.automation-now-tag', root, 'Automation now tag');
};

const requireAutomationTimeGridCanvasInner = (canvas: Element): HTMLElement => {
    const selector = '.automation-time-grid-canvas-inner';
    const inner = resolve(selector, canvas);
    if (inner instanceof HTMLElement) {
        return inner;
    }
    throw new Error('Automation time grid canvas inner missing');
};

const queryAutomationViewToggleButtons = (viewToggle: HTMLElement): HTMLButtonElement[] => {
    return resolveButtonList('button[data-view]', viewToggle, 'Automation view toggle button');
};

const requireAutomationViewCycleButton = (viewToggle: HTMLElement): HTMLButtonElement => {
    const element = resolve('#automation-view-cycle-button', viewToggle);
    if (element instanceof HTMLButtonElement) {
        return element;
    }
    throw new Error('Automation view cycle button missing');
};

const queryAutomationTurnTextareas = (turnsList: HTMLElement): HTMLTextAreaElement[] => {
    return resolveTextareaList('textarea[data-turn-index]', turnsList, 'Automation turn textarea');
};

const queryAutomationColorInputs = (modalId: string, colorPicker: HTMLElement): HTMLInputElement[] => {
    const name = modalUiId(modalId, 'color');
    return resolveInputList(`input[name="${name}"]`, colorPicker, 'Automation color input');
};

const requireAutomationToggleLabel = (toggleSwitch: Element): HTMLElement => {
    const label = resolve('.toggle-label', toggleSwitch);
    if (label instanceof HTMLElement) {
        return label;
    }
    throw new Error('Automation toggle label element missing');
};

const resolveAutomationWeekColumnCanvas = (weekColumn: HTMLElement): HTMLElement => {
    const canvas = resolve('.automation-time-grid-canvas', weekColumn);
    if (canvas instanceof HTMLElement) {
        return canvas;
    }
    throw new Error('Automation week column canvas missing');
};

const optionalAutomationRoot = (host: AutomationDomHost): HTMLElement | null => host.optionalHTMLElement('#automation-root');

const requireAutomationUi = (host: AutomationDomHost): AutomationUiRefs => {
    const root = host.requireHTMLElement('#automation-root');
    const contentWrapper = host.requireHTMLElement('#automation-content-wrapper', root);
    const preferencesCorruptOverlay = host.requireHTMLElement('#automation-preferences-corrupt-overlay', root);
    const rangeTitle = host.requireHTMLElement('#automation-range-title', root);
    const todayButton = narrowButton(host.requireHTMLElement('#automation-today-button', root), 'today button');
    const calendarRoot = host.requireHTMLElement('#automation-calendar-root', root);
    const registryRoot = host.requireHTMLElement('#automation-registry-root', root);
    const registryScroll = host.requireHTMLElement('#automation-registry-scroll', registryRoot);
    const automationsRoot = host.requireHTMLElement('#automation-automations-root', registryScroll);
    const windowRunsRoot = host.requireHTMLElement('#automation-window-runs-root', registryScroll);
    const splitter = host.requireHTMLElement('#automation-splitter', root);
    const viewToggle = host.requireHTMLElement('#automation-view-toggle', root);
    const registryOverlayToggle = narrowButton(host.requireHTMLElement('#automation-registry-overlay-toggle', root), 'registry overlay toggle');

    return {
        root,
        contentWrapper,
        preferencesCorruptOverlay,
        rangeTitle,
        todayButton,
        calendarRoot,
        registryRoot,
        registryScroll,
        automationsRoot,
        windowRunsRoot,
        splitter,
        viewToggle,
        registryOverlayToggle
    };
};

export { optionalAutomationRoot, queryAutomationColorInputs, queryAutomationTurnTextareas, queryAutomationViewToggleButtons, requireAutomationUi, requireAutomationViewCycleButton, resolveAutomationWeekColumnCanvas };
export { optionalAutomationCalendarScroll, optionalAutomationCalendarTrack, queryAutomationCalendarPeriods, requireActionButton, requireAutomationCalendarScroll, requireAutomationCalendarTrack, requireAutomationTimeGridCanvasInner };
export { optionalAutomationMonthDay, optionalAutomationMonthDayHeader, optionalAutomationMonthZones, optionalAutomationZoneChip };
export { queryAutomationNowLines, queryAutomationNowTags };
export { optionalAutomationCalendarLoading, optionalAutomationCalendarStage, requireAutomationCalendarStage, requireAutomationToggleLabel };
