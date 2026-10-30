/* SoAI - Automation page calendar presentation [frontend/assets/ts/pages/automation/controllers/automationCalendarPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHtmlFragment } from '@core/dom/html.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { CHECKERBOARD_CLASS_NAMES } from '@core/dom/checkerboardAssignment.ts';
import { dom } from '@core/dom/dom.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { syncAttributeValue, syncElementShell } from '@core/dom/patching.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { getWeekNumberForWindow, isSameDay, startOfDay, toIsoDate } from '@core/time/localCalendar.ts';
import { buildHourLabels, formatAutomationFullDate, resolveNowLineTopPx } from '@pages/automation/formatting/service.ts';
import { resolveBufferedAutomationWindow, type BufferedAutomationWindowEntry } from '@pages/automation/controllers/automationWindow.ts';
import { formatAutomationCreateAtLabel, formatAutomationOccurrenceLabel, formatAutomationRunTime } from '@pages/automation/controllers/automationZoneFormatters.ts';
import { optionalAutomationCalendarLoading, optionalAutomationCalendarScroll, optionalAutomationCalendarTrack, requireAutomationCalendarStage } from '@pages/automation/dom.ts';
import { renderMonthView } from '@pages/automation/rendering/monthView.ts';
import { AUTOMATION_KEYBOARD_CREATE_DEFAULT_MINUTES, renderDayTimeGrid, renderWeekTimeGrid } from '@pages/automation/rendering/timeGridView.ts';
import type { AutomationOccurrenceResponse } from '@features/automation/public.ts';
import type { AutomationCalendarTimeFormat, AutomationPageState, AutomationUiRefs } from '@pages/automation/types.ts';
import { AUTOMATION_DEFAULT_DISPLAY_DURATION_MS } from '@pages/automation/widgets/calendar/constants.ts';
import { layoutZonesForTimeGrid } from '@pages/automation/widgets/calendar/timeGridLayout.ts';
import type { TimeGridZoneLayout } from '@pages/automation/widgets/calendar/timeGridTypes.ts';

interface AutomationCalendarRenderHost {
    ui: AutomationUiRefs;
    hourHeightPx: number;
}

interface AutomationCalendarRenderCache {
    presentationSignature: string;
}

const groupZonesByIsoDay = (zones: readonly AutomationOccurrenceResponse[]): Map<string, AutomationOccurrenceResponse[]> => {
    const map = new Map<string, AutomationOccurrenceResponse[]>();
    for (const zone of zones) {
        const iso = toIsoDate(startOfDay(new Date(zone.scheduledAtMs)));
        const list = map.get(iso);
        if (list) {
            list.push(zone);
        } else {
            map.set(iso, [zone]);
        }
    }
    return map;
};

const syncCalendarScrollShell = (calendarRoot: HTMLElement, viewMode: AutomationPageState['viewMode']): void => {
    const scroll = optionalAutomationCalendarScroll(calendarRoot);
    if (!scroll) {
        throw new Error('Automation calendar scroll shell missing');
    }
    scroll.className = `automation-calendar-scroll automation-calendar-scroll--${viewMode}`;
};

const renderBufferedPeriod = (entry: BufferedAutomationWindowEntry, content: string): string => {
    const offset = entry.offset;
    const center = offset === 0 ? 'true' : 'false';
    return `<section class="automation-calendar-period automation-calendar-period--${uiAttr(entry.window.viewMode).html}" data-automation-period-offset="${uiAttr(String(offset)).html}" data-automation-period-signature="${uiAttr(entry.signature).html}" data-automation-center-period="${uiAttr(center).html}">${content}</section>`;
};

const buildMonthMarkup = (state: AutomationPageState, zonesByDay: Map<string, AutomationOccurrenceResponse[]>, periods: readonly BufferedAutomationWindowEntry[], maxChipsPerDay: number): string => {
    const now = new Date();
    const renderedPeriods = periods.map((entry) => {
        const window = entry.window;
        if (window.viewMode !== 'month') {
            throw new Error('Expected month window for buffered month rendering');
        }
        const weekDayLabels = window.monthGrid.slice(0, 7).map((date) => i18n.formatDate(date, { weekday: 'short' }));
        const monthLabel = i18n.formatDate(window.focusDate, { month: 'long', year: 'numeric' });
        const weekNumbers = state.calendarSettings.showWeekNumbers
            ? (() => {
                  const numbers: number[] = [];
                  for (let index = 0; index < 6; index += 1) {
                      const anchorIndex = index * 7;
                      const anchor = window.monthGrid[anchorIndex];
                      if (!anchor) {
                          throw new Error(`Automation month grid is missing week anchor at index ${anchorIndex}`);
                      }
                      numbers.push(getWeekNumberForWindow(anchor, window.weekStartsOnSunday, state.calendarSettings.weekNumbering));
                  }
                  return numbers;
              })()
            : [];
        const days = window.monthGrid.map((date) => {
            const iso = toIsoDate(date);
            const zones = zonesByDay.get(iso) ?? [];
            zones.sort((left, right) => left.scheduledAtMs - right.scheduledAtMs);
            return {
                iso,
                label: formatAutomationFullDate(date),
                day: date.getDate(),
                isOutside: date.getMonth() !== window.focusDate.getMonth(),
                isToday: isSameDay(date, now),
                isSelected: isSameDay(date, window.selectedDate),
                zones,
                selectedZoneKey: entry.offset === 0 ? state.selectedZoneKey : null
            };
        });
        return renderBufferedPeriod(entry, renderMonthView({ monthLabel, weekDayLabels, days, showWeekNumbers: state.calendarSettings.showWeekNumbers, weekNumbers, maxChipsPerDay, formatZoneLabel: (zone) => formatAutomationOccurrenceLabel(zone, state.calendarSettings.timeFormat) }));
    });
    return renderedPeriods.join('');
};

const buildWeekMarkup = (state: AutomationPageState, zonesByDay: Map<string, AutomationOccurrenceResponse[]>, periods: readonly BufferedAutomationWindowEntry[], hourHeightPx: number): string => {
    const now = new Date();
    const todayIsoDate = toIsoDate(now);
    const hourLabels = buildHourLabels(state.calendarSettings.timeFormat);
    const formatZoneTime = (utcMs: number): string => formatAutomationRunTime(utcMs, state.calendarSettings.timeFormat);
    const formatZoneLabel = (zone: TimeGridZoneLayout): string => formatAutomationOccurrenceLabel({ title: zone.title, scheduledAtMs: zone.startUtcMs, status: zone.status }, state.calendarSettings.timeFormat);
    const constants = { hourHeightPx, displayDurationMs: AUTOMATION_DEFAULT_DISPLAY_DURATION_MS };
    return periods
        .map((entry) => {
            if (entry.window.viewMode !== 'week') {
                throw new Error('Expected week window for buffered week rendering');
            }
            const dayIsoDates = entry.window.weekDays.map((date) => toIsoDate(date));
            const dayLabels = entry.window.weekDays.map((date) => i18n.formatDate(date, { weekday: 'short', day: '2-digit' }));
            const dayFullLabels = entry.window.weekDays.map((date) => formatAutomationFullDate(date));
            const createLabels = dayIsoDates.map((iso) => formatAutomationCreateAtLabel(iso, AUTOMATION_KEYBOARD_CREATE_DEFAULT_MINUTES, state.calendarSettings.timeFormat));
            const selectedIsoDate = toIsoDate(entry.window.selectedDate);
            const dayZones = entry.window.weekDays.map((date) => {
                const iso = toIsoDate(date);
                return layoutZonesForTimeGrid(zonesByDay.get(iso) ?? [], entry.offset === 0 ? state.selectedZoneKey : null, constants);
            });
            const nowLine = entry.window.weekDays.reduce<{ dayIndex: number; topPx: number } | null>((match, date, index) => {
                if (match) {
                    return match;
                }
                if (isSameDay(date, now)) {
                    return { dayIndex: index, topPx: resolveNowLineTopPx(hourHeightPx, now) };
                }
                return null;
            }, null);
            return renderBufferedPeriod(entry, renderWeekTimeGrid({ dayLabels, dayFullLabels, createLabels, formatZoneLabel, dayIsoDates, dayZones, todayIsoDate, selectedIsoDate, nowLine, hourHeightPx, hourLabels, formatZoneTime }));
        })
        .join('');
};

const buildDayMarkup = (state: AutomationPageState, zonesByDay: Map<string, AutomationOccurrenceResponse[]>, periods: readonly BufferedAutomationWindowEntry[], hourHeightPx: number): string => {
    const now = new Date();
    const hourLabels = buildHourLabels(state.calendarSettings.timeFormat);
    const formatZoneTime = (utcMs: number): string => formatAutomationRunTime(utcMs, state.calendarSettings.timeFormat);
    const formatZoneLabel = (zone: TimeGridZoneLayout): string => formatAutomationOccurrenceLabel({ title: zone.title, scheduledAtMs: zone.startUtcMs, status: zone.status }, state.calendarSettings.timeFormat);
    const constants = { hourHeightPx, displayDurationMs: AUTOMATION_DEFAULT_DISPLAY_DURATION_MS };
    return periods
        .map((entry) => {
            if (entry.window.viewMode !== 'day') {
                throw new Error('Expected day window for buffered day rendering');
            }
            const iso = toIsoDate(entry.window.day);
            const label = formatAutomationFullDate(entry.window.day);
            const zones = zonesByDay.get(iso) ?? [];
            const layouts = layoutZonesForTimeGrid(zones, entry.offset === 0 ? state.selectedZoneKey : null, constants);
            const nowLineTopPx = isSameDay(entry.window.day, now) ? resolveNowLineTopPx(hourHeightPx, now) : null;
            return renderBufferedPeriod(entry, renderDayTimeGrid({ label, createLabel: formatAutomationCreateAtLabel(iso, AUTOMATION_KEYBOARD_CREATE_DEFAULT_MINUTES, state.calendarSettings.timeFormat), isoDate: iso, zones: layouts, nowLineTopPx, hourHeightPx, hourLabels, formatZoneTime, formatZoneLabel }));
        })
        .join('');
};

const buildCalendarMarkup = (state: AutomationPageState, hourHeightPx: number, monthMaxChipsPerDay: number): { markup: string; renderedWindowSignature: string } => {
    const bufferedWindow = resolveBufferedAutomationWindow(state);
    const zonesByDay = groupZonesByIsoDay(state.zones);
    if (state.viewMode === 'month') {
        return {
            markup: buildMonthMarkup(state, zonesByDay, bufferedWindow.periods, monthMaxChipsPerDay),
            renderedWindowSignature: bufferedWindow.signature
        };
    }
    const periodMarkup = state.viewMode === 'week' ? buildWeekMarkup(state, zonesByDay, bufferedWindow.periods, hourHeightPx) : buildDayMarkup(state, zonesByDay, bufferedWindow.periods, hourHeightPx);
    return {
        markup: periodMarkup,
        renderedWindowSignature: bufferedWindow.signature
    };
};

const wrapInPagerTrack = (markup: string): string => `<div class="automation-calendar-track" data-automation-calendar-track="true">${markup}</div>`;

const parseCalendarTrack = (stage: HTMLElement, markup: string): HTMLElement => {
    const fragment = createHtmlFragment({ documentRef: stage.ownerDocument, html: markup, context: stage });
    const track = Array.from(fragment.childNodes).find((node): node is HTMLElement => node instanceof HTMLElement && node.dataset['automationCalendarTrack'] === 'true') ?? null;
    if (!track) {
        throw new Error('Automation calendar track markup missing');
    }
    return track;
};

const CALENDAR_RECONCILIATION_OPTIONS = { preservedClassNames: CHECKERBOARD_CLASS_NAMES, preservedAttributeNames: new Set(['data-checkerboard-id']) };

const reconcileCalendarTrack = (stage: HTMLElement, markup: string, timeFormat: AutomationCalendarTimeFormat): void => {
    const existingTrack = optionalAutomationCalendarTrack(stage);
    if (!existingTrack) {
        stage.replaceChildren(parseCalendarTrack(stage, markup));
        return;
    }
    const nextTrack = parseCalendarTrack(stage, markup);
    syncAttributeValue(existingTrack, 'class', nextTrack.className);
    patchOrderedChildren({
        existingParent: existingTrack,
        createdParent: nextTrack,
        resolveChildKey: (period) => period.dataset['automationPeriodSignature'] ?? null,
        insertChild: (parent, period, anchor) => {
            parent.insertBefore(period, anchor);
            return period;
        },
        patchChild: (existingPeriod, nextPeriod) => {
            const nextCreateControls = dom.resolveAll('[data-automation-keyboard-create="true"]', nextPeriod);
            for (const control of dom.resolveAll('[data-automation-keyboard-create="true"]', existingPeriod)) {
                if (!(control instanceof HTMLButtonElement)) continue;
                const replacement = nextCreateControls.find((candidate) => candidate instanceof HTMLButtonElement && candidate.dataset['date'] === control.dataset['date']);
                if (!(replacement instanceof HTMLButtonElement)) continue;
                const minutes = control.dataset['keyboardMinutes'];
                if (minutes === undefined) continue;
                replacement.dataset['keyboardMinutes'] = minutes;
                const label = formatAutomationCreateAtLabel(replacement.dataset['date'] ?? '', Number(minutes), timeFormat);
                replacement.setAttribute('aria-label', label);
                setTooltipText(replacement, label);
            }
            const shellChanged = syncElementShell({ target: existingPeriod, source: nextPeriod });
            return reconcileChildNodes(existingPeriod, Array.from(nextPeriod.childNodes), CALENDAR_RECONCILIATION_OPTIONS) || shellChanged;
        },
        removeChild: (period) => period.remove(),
        replaceUnsupportedChildren: () => {
            existingTrack.replaceChildren(...Array.from(nextTrack.childNodes));
            return true;
        }
    });
};

const renderAutomationCalendar = (state: AutomationPageState, host: AutomationCalendarRenderHost, cache: AutomationCalendarRenderCache, monthMaxChipsPerDay: number): string => {
    const presentation = buildCalendarMarkup(state, host.hourHeightPx, monthMaxChipsPerDay);
    const presentationSignature = `${presentation.renderedWindowSignature}:${presentation.markup}`;
    const loading = optionalAutomationCalendarLoading(host.ui.calendarRoot);
    if (loading) {
        loading.remove();
    }
    syncCalendarScrollShell(host.ui.calendarRoot, state.viewMode);
    if (cache.presentationSignature === presentationSignature) {
        return presentation.renderedWindowSignature;
    }
    const stage = requireAutomationCalendarStage(host.ui.calendarRoot);
    reconcileCalendarTrack(stage, wrapInPagerTrack(presentation.markup), state.calendarSettings.timeFormat);
    cache.presentationSignature = presentationSignature;
    return presentation.renderedWindowSignature;
};

export { renderAutomationCalendar };
export type { AutomationCalendarRenderCache, AutomationCalendarRenderHost };
