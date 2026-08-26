/* SoAI - Automation page month view [frontend/assets/ts/pages/automation/rendering/monthView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { uiAttr, uiText } from '@core/security/uiHtml.ts';
import { AUTOMATION_ACTION_SELECT_DAY, AUTOMATION_ACTION_SELECT_ZONE, type AutomationZone } from '@features/automation/public.ts';
import { buildAutomationZoneKeyForZone } from '@pages/automation/contracts/zoneKey.ts';
import { resolveAutomationRunStatusContainerClass } from '@pages/automation/controllers/automationZoneFormatters.ts';
import { renderAutomationColorAttribute } from '@pages/automation/rendering/automationColorMarkup.ts';

const clampSparkPos = (value: number): number => clampNumber(value, 0.02, 0.98);

const resolveSparkPos = (utcMs: number): number => {
    const date = new Date(utcMs);
    const minutes = date.getHours() * 60 + date.getMinutes();
    return clampSparkPos(minutes / 1440);
};

const renderSparklineMarkers = (zones: readonly AutomationZone[]): string => {
    const MAX_MARKERS = 12;
    if (zones.length === 0) {
        return '';
    }

    if (zones.length <= MAX_MARKERS) {
        return zones
            .map((zone) => {
                const colorAttr = renderAutomationColorAttribute(zone.color);
                const pos = resolveSparkPos(zone.scheduledAtMs);
                return `<span class="automation-month-sparkline-marker"${colorAttr} style="--spark-pos:${uiAttr(String(pos)).html};--spark-size:3px;"></span>`;
            })
            .join('');
    }

    const bins: { count: number; color: AutomationZone['color'] }[] = Array.from({ length: MAX_MARKERS }).map(() => ({ count: 0, color: null }));
    for (const zone of zones) {
        const pos = resolveSparkPos(zone.scheduledAtMs);
        const index = clampNumber(Math.floor(pos * MAX_MARKERS), 0, MAX_MARKERS - 1);
        const bin = bins[index];
        if (!bin) {
            continue;
        }
        bin.count += 1;
        if (!bin.color) {
            bin.color = zone.color;
        }
    }

    return bins
        .map((bin, index) => {
            if (bin.count === 0) {
                return '';
            }
            const weight = clampNumber(bin.count, 1, 4);
            const sizePx = 2 + weight;
            const pos = clampSparkPos((index + 0.5) / MAX_MARKERS);
            const colorAttr = renderAutomationColorAttribute(bin.color);
            return `<span class="automation-month-sparkline-marker"${colorAttr} style="--spark-pos:${uiAttr(String(pos)).html};--spark-size:${uiAttr(`${sizePx}px`).html};"></span>`;
        })
        .join('');
};

const renderMonthView = (options: {
    monthLabel: string;
    weekDayLabels: readonly string[];
    showWeekNumbers: boolean;
    weekNumbers: readonly number[];
    maxChipsPerDay: number;
    days: readonly {
        iso: string;
        day: number;
        isOutside: boolean;
        isToday: boolean;
        isSelected: boolean;
        zones: readonly AutomationZone[];
        selectedZoneKey: string | null;
    }[];
}): string => {
    const weekdayCells: string[] = [];
    if (options.showWeekNumbers) {
        weekdayCells.push(`<div class="automation-month-weekday automation-month-weekday--weeknumber" aria-hidden="true"></div>`);
    }
    weekdayCells.push(...options.weekDayLabels.map((label) => `<div class="automation-month-weekday">${uiText(label).html}</div>`));
    const weekdayMarkup = weekdayCells.join('');
    const monthHeadingMarkup = `<div class="automation-month-heading">${uiText(options.monthLabel).html}</div>`;

    const maxZones = options.maxChipsPerDay;
    const anySparkline = options.days.some((entry) => entry.zones.length > 0 && (maxZones === 0 || entry.zones.length > maxZones));

    const dayCellMarkup = options.days.map((entry) => {
        const classes = ['automation-month-day'];
        if (entry.isOutside) classes.push('is-outside');
        if (entry.isToday) classes.push('is-today');
        if (entry.isSelected) classes.push('is-selected');

        const visibleZones = maxZones > 0 ? entry.zones.slice(0, maxZones) : [];
        const showSparkline = entry.zones.length > 0 && (maxZones === 0 || entry.zones.length > maxZones);
        if (showSparkline) classes.push('has-sparkline');

        const countBadgeText = (() => {
            if (entry.zones.length === 0) {
                return '';
            }
            if (entry.zones.length >= 10) {
                return i18n.t('automation.calendar.countOverflow');
            }
            return String(entry.zones.length);
        })();
        const countBadgeMarkup = countBadgeText ? `<span class="automation-month-day-count automation-month-day-count-badge">${uiText(countBadgeText).html}</span>` : '';
        const dayLabel = String(entry.day);

        const zones = visibleZones
            .map((zone) => {
                const key = buildAutomationZoneKeyForZone(zone);
                const selected = entry.selectedZoneKey === key ? ' is-selected' : '';
                const statusClass = resolveAutomationRunStatusContainerClass(zone.status);
                const colorAttr = renderAutomationColorAttribute(zone.color);
                return `<button type="button" class="automation-zone-chip ${uiAttr(statusClass).html}${selected}"${colorAttr} data-run-status="${uiAttr(zone.status).html}" data-action="${uiAttr(AUTOMATION_ACTION_SELECT_ZONE).html}" data-zone-key="${uiAttr(key).html}" aria-label="${uiAttr(zone.title).html}" data-tooltip="${uiAttr(zone.title).html}">` + `<span class="automation-zone-chip-title">${uiText(zone.title).html}</span>` + `</button>`;
            })
            .join('');
        const sparklineMarkup = showSparkline ? `<div class="automation-month-sparkline" aria-hidden="true">${renderSparklineMarkers(entry.zones)}</div>` : '';
        return `<div class="${uiAttr(classes.join(' ')).html}" data-action="${uiAttr(AUTOMATION_ACTION_SELECT_DAY).html}" data-date="${uiAttr(entry.iso).html}" role="button" tabindex="0" aria-label="${uiAttr(dayLabel).html}" data-tooltip="${uiAttr(dayLabel).html}">` + `${sparklineMarkup}` + `<div class="automation-month-day-header"><span class="automation-month-day-number">${uiText(String(entry.day)).html}</span>${countBadgeMarkup}</div>` + `<div class="automation-month-zones">${zones}</div>` + `</div>`;
    });

    let dayCells = '';
    if (!options.showWeekNumbers) {
        dayCells = dayCellMarkup.join('');
    } else {
        const weeks = options.weekNumbers.slice(0, 6);
        for (let row = 0; row < 6; row += 1) {
            const weekNumber = weeks[row];
            if (!Number.isFinite(weekNumber)) {
                throw new Error('Month view week numbers missing');
            }
            dayCells += `<div class="automation-month-weeknumber">${uiText(String(weekNumber)).html}</div>`;
            const start = row * 7;
            dayCells += dayCellMarkup.slice(start, start + 7).join('');
        }
    }

    const rootClasses = ['automation-month'];
    if (options.showWeekNumbers) rootClasses.push('has-week-numbers');
    if (anySparkline) rootClasses.push('has-sparklines');
    return `<div class="${uiAttr(rootClasses.join(' ')).html}">${monthHeadingMarkup}<div class="automation-month-weekdays">${weekdayMarkup}</div><div class="automation-month-grid">${dayCells}</div></div>`;
};

export { renderMonthView };
