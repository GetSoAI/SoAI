/* SoAI - Automation page time grid view [frontend/assets/ts/pages/automation/rendering/timeGridView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

import { uiAttr, uiText } from '@core/security/uiHtml.ts';
import { AUTOMATION_ACTION_SELECT_DAY, AUTOMATION_ACTION_SELECT_ZONE, AUTOMATION_ACTION_TIME_GRID_CREATE_AT } from '@features/automation/public.ts';
import type { AutomationHourLabel } from '@pages/automation/formatting/service.ts';
import { resolveAutomationRunStatusContainerClass } from '@pages/automation/controllers/automationZoneFormatters.ts';
import { renderAutomationColorAttribute } from '@pages/automation/rendering/automationColorMarkup.ts';
import type { TimeGridZoneLayout } from '@pages/automation/widgets/calendar/timeGridTypes.ts';

const renderHourMarker = (label: AutomationHourLabel, hour: number, hourHeightPx: number): string => {
    if (hour === 0) return '';
    const secondary = label.secondary ? `<span class="automation-time-grid-hour-secondary">${uiText(label.secondary).html}</span>` : '';
    return `<div class="automation-time-grid-hour" style="top:${uiAttr(String(hour * hourHeightPx)).html}px"><span class="automation-time-grid-hour-primary">${uiText(label.primary).html}</span>${secondary}</div>`;
};

const renderZoneBlock = (zone: TimeGridZoneLayout, when: string): string => {
    const selected = zone.isSelected ? ' is-selected' : '';
    const compact = zone.heightPx < 34 ? ' is-compact' : '';
    const meta = compact ? '' : `<div class="automation-zone-block-meta">${uiText(when).html}</div>`;
    const colorAttr = renderAutomationColorAttribute(zone.color);
    const statusClass = resolveAutomationRunStatusContainerClass(zone.status);
    return `<button type="button" class="automation-zone-block ${uiAttr(statusClass).html}${selected}${compact}"${colorAttr} data-run-status="${uiAttr(zone.status).html}" data-action="${uiAttr(AUTOMATION_ACTION_SELECT_ZONE).html}" data-zone-key="${uiAttr(zone.key).html}" style="top:${uiAttr(String(zone.topPx)).html}px;height:${uiAttr(String(zone.heightPx)).html}px;left:${uiAttr(String(zone.leftPct)).html}%;width:${uiAttr(String(zone.widthPct)).html}%" aria-label="${uiAttr(zone.title).html}" data-tooltip="${uiAttr(zone.title).html}">` + `<div class="automation-zone-block-title">${uiText(zone.title).html}</div>` + meta + `</button>`;
};

const renderTimeGridSlots = (hourHeightPx: number): string => {
    return `<div class="automation-time-grid-slots" aria-hidden="true">` + Array.from({ length: 24 }, (_unusedValue, hour) => `<div class="automation-time-grid-slot" style="top:${uiAttr(String(hour * hourHeightPx)).html}px;height:${uiAttr(String(hourHeightPx)).html}px;"></div>`).join('') + `</div>`;
};

const renderEmptyDayLabel = (label: string, zones: readonly TimeGridZoneLayout[]): string => {
    const normalizedLabel = label.trim();
    return zones.length === 0 && normalizedLabel ? `<div class="automation-time-grid-empty-day-label">${uiText(normalizedLabel).html}</div>` : '';
};

const renderDayTimeGrid = (options: { label: string; dayName: string; isoDate: string; zones: readonly TimeGridZoneLayout[]; nowLineTopPx: number | null; hourHeightPx: number; hourLabels: readonly AutomationHourLabel[]; formatZoneTime: (utcMs: number) => string }): string => {
    const hourMarkers = options.hourLabels
        .slice(0, 24)
        .map((label, hour) => renderHourMarker(label, hour, options.hourHeightPx))
        .join('');

    const nowLine = options.nowLineTopPx === null ? '' : `<div class="automation-now-line" style="top:${uiAttr(String(options.nowLineTopPx)).html}px"></div>`;
    const nowGutterTag = options.nowLineTopPx === null ? '' : `<div class="automation-now-tag" style="top:${uiAttr(String(options.nowLineTopPx)).html}px">${uiText(i18n.t('automation.calendar.now')).html}</div>`;
    const nowIndicator = options.nowLineTopPx === null ? '' : `<div class="automation-now-indicator" aria-hidden="true">${nowLine}${nowGutterTag}</div>`;
    const heading = `<div class="automation-day-heading">${uiText(options.label).html}</div>`;

    const blocks = options.zones
        .map((zone) => {
            const when = options.formatZoneTime(zone.startUtcMs);
            return renderZoneBlock(zone, when);
        })
        .join('');

    return `<div class="automation-time-grid automation-time-grid--day" data-automation-view="day">` + `${heading}` + `<div class="automation-time-grid-scroll-inner">` + `${nowIndicator}` + `<div class="automation-time-grid-gutter"><div class="automation-time-grid-hours">${hourMarkers}</div></div>` + `<div class="automation-time-grid-canvas automation-time-grid-canvas--day checkerboard-light" role="button" tabindex="0" aria-label="${uiAttr(options.label).html}" data-action="${uiAttr(AUTOMATION_ACTION_TIME_GRID_CREATE_AT).html}" data-automation-day-canvas="true" data-keyboard-minutes="540" data-date="${uiAttr(options.isoDate).html}">` + `<div class="automation-time-grid-canvas-inner">` + `${renderTimeGridSlots(options.hourHeightPx)}${renderEmptyDayLabel(options.dayName, options.zones)}${blocks}` + `</div>` + `</div>` + `</div>` + `</div>`;
};

const renderWeekTimeGrid = (options: { dayLabels: readonly string[]; dayIsoDates: readonly string[]; dayZones: readonly TimeGridZoneLayout[][]; todayIsoDate: string; selectedIsoDate: string; nowLine: { dayIndex: number; topPx: number } | null; hourHeightPx: number; hourLabels: readonly AutomationHourLabel[]; formatZoneTime: (utcMs: number) => string }): string => {
    const hourMarkers = options.hourLabels
        .slice(0, 24)
        .map((label, hour) => renderHourMarker(label, hour, options.hourHeightPx))
        .join('');

    const headerButtons = options.dayLabels
        .map((label, index) => {
            const iso = options.dayIsoDates[index] ?? '';
            const isToday = iso !== '' && iso === options.todayIsoDate;
            const isSelected = iso !== '' && iso === options.selectedIsoDate;
            const classes = ['automation-week-header-day', 'ui-button', isToday && isSelected ? 'ui-variant-accent' : 'ui-variant-neutral'];
            if (isToday) classes.push('is-today');
            if (isSelected) classes.push('is-selected', 'is-active');
            return `<button type="button" class="${uiAttr(classes.join(' ')).html}" data-action="${uiAttr(AUTOMATION_ACTION_SELECT_DAY).html}" data-date="${uiAttr(iso).html}" aria-label="${uiAttr(label).html}" data-tooltip="${uiAttr(label).html}">${uiText(label).html}</button>`;
        })
        .join('');

    const dayColumns = options.dayZones
        .map((zones, dayIndex) => {
            const iso = options.dayIsoDates[dayIndex] ?? '';
            const columnClasses = ['automation-week-column'];
            if (iso && iso === options.todayIsoDate) columnClasses.push('is-today');
            if (iso && iso === options.selectedIsoDate) columnClasses.push('is-selected');
            const nowLine = options.nowLine && options.nowLine.dayIndex === dayIndex ? `<div class="automation-now-line" style="top:${uiAttr(String(options.nowLine.topPx)).html}px"></div>` : '';
            const blocks = zones
                .map((zone) => {
                    const when = options.formatZoneTime(zone.startUtcMs);
                    return renderZoneBlock(zone, when);
                })
                .join('');

            return `<div class="${uiAttr(columnClasses.join(' ')).html}" role="button" tabindex="0" aria-label="${uiAttr(options.dayLabels[dayIndex] ?? iso).html}" data-action="${uiAttr(AUTOMATION_ACTION_TIME_GRID_CREATE_AT).html}" data-automation-week-column="true" data-keyboard-minutes="540" data-date="${uiAttr(iso).html}">` + `<div class="automation-time-grid-canvas automation-time-grid-canvas--week">` + `<div class="automation-time-grid-canvas-inner">${renderTimeGridSlots(options.hourHeightPx)}${nowLine}${blocks}</div>` + `</div>` + `</div>`;
        })
        .join('');

    return `<div class="automation-week" data-automation-view="week">` + `<div class="automation-week-header">` + `<div class="automation-week-header-gutter"></div>` + `<div class="automation-week-header-days">${headerButtons}</div>` + `</div>` + `<div class="automation-time-grid automation-time-grid--week">` + `<div class="automation-time-grid-scroll-inner automation-time-grid-scroll-inner--week">` + `<div class="automation-time-grid-gutter"><div class="automation-time-grid-hours">${hourMarkers}</div></div>` + `<div class="automation-week-columns">${dayColumns}</div>` + `</div>` + `</div>` + `</div>`;
};

export { renderDayTimeGrid, renderWeekTimeGrid };
