/* SoAI - Automation page calendar presentation [frontend/assets/ts/pages/automation/controllers/automationCalendarPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHtmlFragment } from '@core/dom/html.ts';
import { replaceChildrenIfChanged, syncElementShell } from '@core/dom/patching.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { getWeekNumberForWindow, isSameDay, startOfDay, toIsoDate } from '@core/time/localCalendar.ts';
import { buildHourLabels, resolveNowLineTopPx } from '@pages/automation/formatting/service.ts';
import { resolveBufferedAutomationWindow, type BufferedAutomationWindowEntry } from '@pages/automation/controllers/automationWindow.ts';
import { formatAutomationRunTime } from '@pages/automation/controllers/automationZoneFormatters.ts';
import { optionalAutomationCalendarLoading, optionalAutomationCalendarScroll, optionalAutomationCalendarTrack, requireAutomationCalendarStage } from '@pages/automation/dom.ts';
import { renderMonthView } from '@pages/automation/rendering/monthView.ts';
import { renderDayTimeGrid, renderWeekTimeGrid } from '@pages/automation/rendering/timeGridView.ts';
import type { AutomationZone } from '@features/automation/public.ts';
import type { AutomationPageState, AutomationUiRefs } from '@pages/automation/types.ts';
import { AUTOMATION_DEFAULT_DISPLAY_DURATION_MS } from '@pages/automation/widgets/calendar/constants.ts';
import { layoutZonesForTimeGrid } from '@pages/automation/widgets/calendar/timeGridLayout.ts';

interface AutomationCalendarRenderHost {
    ui: AutomationUiRefs;
    hourHeightPx: number;
}

interface AutomationCalendarRenderCache {
    presentationSignature: string;
}

const groupZonesByIsoDay = (zones: readonly AutomationZone[]): Map<string, AutomationZone[]> => {
    const map = new Map<string, AutomationZone[]>();
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
    scroll.style.setProperty('--automation-calendar-viewport-height', `${scroll.clientHeight}px`);
};

const renderBufferedPeriod = (entry: BufferedAutomationWindowEntry, content: string): string => {
    const offset = entry.offset;
    const center = offset === 0 ? 'true' : 'false';
    return `<section class="automation-calendar-period automation-calendar-period--${uiAttr(entry.window.viewMode).html}" data-automation-period-offset="${uiAttr(String(offset)).html}" data-automation-period-signature="${uiAttr(entry.signature).html}" data-automation-center-period="${uiAttr(center).html}">${content}</section>`;
};

const buildMonthMarkup = (state: AutomationPageState, zonesByDay: Map<string, AutomationZone[]>, periods: readonly BufferedAutomationWindowEntry[], maxChipsPerDay: number): string => {
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
                day: date.getDate(),
                isOutside: date.getMonth() !== window.focusDate.getMonth(),
                isToday: isSameDay(date, now),
                isSelected: isSameDay(date, window.selectedDate),
                zones,
                selectedZoneKey: entry.offset === 0 ? state.selectedZoneKey : null
            };
        });
        return renderBufferedPeriod(entry, renderMonthView({ monthLabel, weekDayLabels, days, showWeekNumbers: state.calendarSettings.showWeekNumbers, weekNumbers, maxChipsPerDay }));
    });
    return renderedPeriods.join('');
};

const buildWeekMarkup = (state: AutomationPageState, zonesByDay: Map<string, AutomationZone[]>, periods: readonly BufferedAutomationWindowEntry[], hourHeightPx: number): string => {
    const now = new Date();
    const todayIsoDate = toIsoDate(now);
    const hourLabels = buildHourLabels(state.calendarSettings.timeFormat);
    const formatZoneTime = (utcMs: number): string => formatAutomationRunTime(utcMs, state.calendarSettings.timeFormat);
    const constants = { hourHeightPx, displayDurationMs: AUTOMATION_DEFAULT_DISPLAY_DURATION_MS };
    return periods
        .map((entry) => {
            if (entry.window.viewMode !== 'week') {
                throw new Error('Expected week window for buffered week rendering');
            }
            const dayIsoDates = entry.window.weekDays.map((date) => toIsoDate(date));
            const dayLabels = entry.window.weekDays.map((date) => i18n.formatDate(date, { weekday: 'short', day: '2-digit' }));
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
            return renderBufferedPeriod(entry, renderWeekTimeGrid({ dayLabels, dayIsoDates, dayZones, todayIsoDate, selectedIsoDate, nowLine, hourHeightPx, hourLabels, formatZoneTime }));
        })
        .join('');
};

const buildDayMarkup = (state: AutomationPageState, zonesByDay: Map<string, AutomationZone[]>, periods: readonly BufferedAutomationWindowEntry[], hourHeightPx: number): string => {
    const now = new Date();
    const hourLabels = buildHourLabels(state.calendarSettings.timeFormat);
    const formatZoneTime = (utcMs: number): string => formatAutomationRunTime(utcMs, state.calendarSettings.timeFormat);
    const constants = { hourHeightPx, displayDurationMs: AUTOMATION_DEFAULT_DISPLAY_DURATION_MS };
    return periods
        .map((entry) => {
            if (entry.window.viewMode !== 'day') {
                throw new Error('Expected day window for buffered day rendering');
            }
            const iso = toIsoDate(entry.window.day);
            const label = i18n.formatDate(entry.window.day, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
            const zones = zonesByDay.get(iso) ?? [];
            const layouts = layoutZonesForTimeGrid(zones, entry.offset === 0 ? state.selectedZoneKey : null, constants);
            const nowLineTopPx = isSameDay(entry.window.day, now) ? resolveNowLineTopPx(hourHeightPx, now) : null;
            return renderBufferedPeriod(entry, renderDayTimeGrid({ label, isoDate: iso, zones: layouts, nowLineTopPx, hourHeightPx, hourLabels, formatZoneTime }));
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

const reconcileCalendarTrack = (stage: HTMLElement, markup: string): void => {
    const existingTrack = optionalAutomationCalendarTrack(stage);
    if (!existingTrack) {
        stage.replaceChildren(parseCalendarTrack(stage, markup));
        return;
    }
    const nextTrack = parseCalendarTrack(stage, markup);
    existingTrack.className = nextTrack.className;
    const nextPeriods = Array.from(nextTrack.children).filter((child): child is HTMLElement => child instanceof HTMLElement);
    const existingPeriods = Array.from(existingTrack.children).filter((child): child is HTMLElement => child instanceof HTMLElement);
    const reusable = new Map<string, HTMLElement>();
    for (const period of existingPeriods) {
        const signature = period.dataset['automationPeriodSignature'];
        if (signature) {
            reusable.set(signature, period);
        }
    }
    const ordered = nextPeriods.map((nextPeriod) => {
        const signature = nextPeriod.dataset['automationPeriodSignature'];
        const existingPeriod = signature ? (reusable.get(signature) ?? null) : null;
        if (!existingPeriod) {
            return nextPeriod;
        }
        syncElementShell({ target: existingPeriod, source: nextPeriod });
        replaceChildrenIfChanged(existingPeriod, nextPeriod);
        return existingPeriod;
    });
    existingTrack.replaceChildren(...ordered);
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
    reconcileCalendarTrack(stage, wrapInPagerTrack(presentation.markup));
    cache.presentationSignature = presentationSignature;
    return presentation.renderedWindowSignature;
};

export { renderAutomationCalendar };
export type { AutomationCalendarRenderCache, AutomationCalendarRenderHost };
