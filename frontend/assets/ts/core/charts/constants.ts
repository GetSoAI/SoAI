/* SoAI - Shared charts constants [frontend/assets/ts/core/charts/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject } from '@core/typeGuards.ts';

interface ChartPadding {
    top: number;
    right: number;
    bottom: number;
    left: number;
}

const DEFAULT_CHART_PADDING: Readonly<ChartPadding> = Object.freeze({
    top: 45,
    right: 60,
    bottom: 20,
    left: 30
});

const DEFAULT_CHART_TYPE_SEQUENCE: readonly string[] = Object.freeze(['precision-line', 'area', 'deviation', 'bar', 'candlestick']);

const HISTORY_CHART_MIN_HEIGHT = 40;

const DEFAULT_PRIMARY_BOTTOM_AXIS_PADDING = 14;

const CHART_PADDING_KEYS = ['top', 'right', 'bottom', 'left'] satisfies ReadonlyArray<keyof ChartPadding>;

const INTERACTION_CLASS_MAP: Readonly<Record<string, string>> = Object.freeze({
    pan: 'is-pan-active',
    yAxis: 'is-y-resize-active',
    xAxis: 'is-x-resize-active'
});

const DOUBLE_TAP_CONFIG = Object.freeze({
    timeThreshold: 300,
    distanceThreshold: 25
});

const LOG_SCOPE = 'ChartInteractions';

const resolveChartPadding = (overrides: Partial<ChartPadding> | null | undefined): ChartPadding => {
    const resolved: ChartPadding = { ...DEFAULT_CHART_PADDING };
    if (!isObject(overrides)) return resolved;
    for (const key of CHART_PADDING_KEYS) {
        const value = Number(overrides[key]);
        if (Number.isFinite(value) && value >= 0) resolved[key] = value;
    }
    return resolved;
};

export { DEFAULT_CHART_PADDING, DEFAULT_CHART_TYPE_SEQUENCE, DEFAULT_PRIMARY_BOTTOM_AXIS_PADDING, DOUBLE_TAP_CONFIG, HISTORY_CHART_MIN_HEIGHT, INTERACTION_CLASS_MAP, LOG_SCOPE, resolveChartPadding };
export type { ChartPadding };
