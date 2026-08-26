/* SoAI - Automation page time grid layout [frontend/assets/ts/pages/automation/widgets/calendar/timeGridLayout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { buildAutomationZoneKeyForZone } from '@pages/automation/contracts/zoneKey.ts';
import type { AutomationZone } from '@features/automation/public.ts';
import type { TimeGridZoneLayout } from '@pages/automation/widgets/calendar/timeGridTypes.ts';

interface CalendarDisplayConstants {
    hourHeightPx: number;
    displayDurationMs: number;
}

interface LayoutInterval {
    key: string;
    title: string;
    startUtcMs: number;
    startMinutes: number;
    endMinutes: number;
    isSelected: boolean;
    status: AutomationZone['status'];
    color: AutomationZone['color'];
}

const minutesFromMidnightLocal = (utcMs: number): number => {
    const date = new Date(utcMs);
    const hours = date.getHours();
    const minutes = date.getMinutes();
    return hours * 60 + minutes;
};

const clusterIntervals = (intervals: readonly LayoutInterval[]): LayoutInterval[][] => {
    if (!intervals.length) {
        return [];
    }
    const clusters: LayoutInterval[][] = [];
    let current: LayoutInterval[] = [];
    let clusterEnd = intervals[0]?.endMinutes ?? 0;
    for (const interval of intervals) {
        if (!current.length) {
            current = [interval];
            clusterEnd = interval.endMinutes;
            continue;
        }
        if (interval.startMinutes < clusterEnd) {
            current.push(interval);
            clusterEnd = Math.max(clusterEnd, interval.endMinutes);
            continue;
        }
        clusters.push(current);
        current = [interval];
        clusterEnd = interval.endMinutes;
    }
    if (current.length) {
        clusters.push(current);
    }
    return clusters;
};

const assignColumns = (cluster: readonly LayoutInterval[]): Map<string, { column: number; columnCount: number }> => {
    const columnsEndMinutes: number[] = [];
    const placement = new Map<string, { column: number; columnCount: number }>();

    for (const interval of cluster) {
        let assigned = -1;
        for (let col = 0; col < columnsEndMinutes.length; col += 1) {
            const columnEnd = columnsEndMinutes[col];
            if (columnEnd === undefined) {
                throw new Error(`Time grid column ${col} end is missing`);
            }
            if (interval.startMinutes >= columnEnd) {
                assigned = col;
                columnsEndMinutes[col] = interval.endMinutes;
                break;
            }
        }
        if (assigned === -1) {
            assigned = columnsEndMinutes.length;
            columnsEndMinutes.push(interval.endMinutes);
        }
        placement.set(interval.key, { column: assigned, columnCount: 0 });
    }

    const columnCount = Math.max(1, columnsEndMinutes.length);
    for (const entry of placement.values()) {
        entry.columnCount = columnCount;
    }
    return placement;
};

const layoutZonesForTimeGrid = (zones: readonly AutomationZone[], selectedZoneKey: string | null, constants: CalendarDisplayConstants): TimeGridZoneLayout[] => {
    const durationMinutes = constants.displayDurationMs / 60000;
    const heightPx = Math.max(18, (durationMinutes / 60) * constants.hourHeightPx);

    const intervals: LayoutInterval[] = zones
        .map((zone) => {
            const startMinutes = minutesFromMidnightLocal(zone.scheduledAtMs);
            const endMinutes = clampNumber(startMinutes + durationMinutes, 0, 24 * 60);
            const key = buildAutomationZoneKeyForZone(zone);
            return {
                key,
                title: zone.title,
                startUtcMs: zone.scheduledAtMs,
                startMinutes,
                endMinutes,
                isSelected: selectedZoneKey === key,
                status: zone.status,
                color: zone.color
            };
        })
        .sort((firstValue, secondValue) => firstValue.startMinutes - secondValue.startMinutes);

    const clusters = clusterIntervals(intervals);
    const placementByKey = new Map<string, { column: number; columnCount: number }>();
    for (const cluster of clusters) {
        const placement = assignColumns(cluster);
        for (const [key, entry] of placement.entries()) {
            placementByKey.set(key, entry);
        }
    }

    return intervals.map((interval) => {
        const placement = placementByKey.get(interval.key);
        if (!placement) {
            throw new Error('Time grid interval placement missing');
        }
        const columnCount = placement.columnCount;
        const widthPct = 100 / columnCount;
        const leftPct = placement.column * widthPct;
        const topPx = (interval.startMinutes / 60) * constants.hourHeightPx;

        return {
            key: interval.key,
            title: interval.title,
            startUtcMs: interval.startUtcMs,
            topPx,
            heightPx,
            leftPct,
            widthPct,
            isSelected: interval.isSelected,
            status: interval.status,
            color: interval.color
        };
    });
};

export { layoutZonesForTimeGrid };
