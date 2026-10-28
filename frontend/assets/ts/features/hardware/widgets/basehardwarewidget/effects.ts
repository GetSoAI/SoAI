/* SoAI - Base hardware widget effects [frontend/assets/ts/features/hardware/widgets/basehardwarewidget/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import type { DataPoint, MetricChartNormalizer } from '@features/hardware/widgets/contracts.ts';
import { type ChartPoint, buildChartSeries, createSmoothPathValues } from '@features/hardware/widgets/mappers.ts';
import { SCALE_CONFIG, WIDGET_CONSTANTS } from '@features/hardware/widgets/constants.ts';
import type { ChartPathValues } from '@features/hardware/widgets/basehardwarewidget/types.ts';

const resolveWidgetWindowDurationMs = (): number => {
    const scaleConfig = SCALE_CONFIG['5m'];
    return scaleConfig ? scaleConfig.durationMs : 300_000;
};

const appendLiveDataPoint = (points: ReadonlyArray<DataPoint>, point: DataPoint, now: number): DataPoint[] => {
    const nextPoints = [...points.filter((existing) => existing.timestamp !== point.timestamp), point];
    const cutoff = now - resolveWidgetWindowDurationMs();
    while (nextPoints.length > 0) {
        const first = nextPoints[0];
        if (!first) {
            break;
        }
        if (first.timestamp >= cutoff) {
            break;
        }
        nextPoints.shift();
    }
    return nextPoints;
};

const trimHistoricalDataPoints = (points: ReadonlyArray<DataPoint>): DataPoint[] => {
    if (points.length === 0) {
        return [];
    }
    const lastPoint = points[points.length - 1];
    if (!lastPoint) {
        throw new Error('Expected last historical data point to exist');
    }
    const cutoff = lastPoint.timestamp - resolveWidgetWindowDurationMs();
    return points.filter((point) => point.timestamp >= cutoff);
};

const identityChartNormalizer: MetricChartNormalizer = (value: number): number => value;

const buildSinglePointSeries = (point: DataPoint, metric: string, now: number, normalizeMetricValue: MetricChartNormalizer): ChartPoint[] => {
    const viewBox = WIDGET_CONSTANTS.SVG_VIEWBOX;
    const rawValue = point[metric];
    if (!isFiniteNumber(rawValue) || point.timestamp < now - resolveWidgetWindowDurationMs()) return [];
    const value = rawValue;
    const normalizedValue = clampNumber(normalizeMetricValue(value, metric), 0, 100);
    const yCoordinate = viewBox - (normalizedValue / 100) * viewBox;
    return [
        { x: 0, y: yCoordinate },
        { x: clampNumber(((point.timestamp - now + resolveWidgetWindowDurationMs()) / resolveWidgetWindowDurationMs()) * viewBox, 0, viewBox), y: yCoordinate }
    ];
};

const buildWidgetChartSeries = (points: ReadonlyArray<DataPoint>, metric: string, now: number, normalizeMetricValue: MetricChartNormalizer = identityChartNormalizer): ChartPoint[] => {
    if (points.length === 0) return [];
    if (points.length === 1) {
        const point = points[0];
        if (!point) throw new Error('Expected widget chart point to exist when points.length === 1');
        return buildSinglePointSeries(point, metric, now, normalizeMetricValue);
    }
    const normalizedPoints = buildChartSeries(points, metric, now, resolveWidgetWindowDurationMs(), WIDGET_CONSTANTS.SVG_VIEWBOX, normalizeMetricValue);
    return normalizedPoints.length >= 2 ? normalizedPoints : [];
};

const buildWidgetChartPathValues = (points: ReadonlyArray<DataPoint>, metric: string, now: number, normalizeMetricValue: MetricChartNormalizer = identityChartNormalizer): ChartPathValues => {
    const series = buildWidgetChartSeries(points, metric, now, normalizeMetricValue);
    return createSmoothPathValues(series, WIDGET_CONSTANTS.SVG_VIEWBOX);
};

export { appendLiveDataPoint, buildWidgetChartPathValues, buildWidgetChartSeries, resolveWidgetWindowDurationMs, trimHistoricalDataPoints };
