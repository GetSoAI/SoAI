/* SoAI - Charts feature history point budget [frontend/assets/ts/features/charts/historyPointBudget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { minutesToMs, msToMinutes } from '@core/time/durations.ts';
import type { HistoryChartInstance } from '@features/charts/historyChartContracts.ts';

interface HistoryChartPointBudgetConfig {
    monitoringIntervalMs: number;
    chartHardLimit: number;
    historyApiPointCap: number;
    maxHistoryPoints: number;
    maxRetentionMinutes: number | null;
    candlestickActive: boolean;
    candlestickIntervalMinutes: number;
    plotWidthPx: number;
}

const HISTORY_CHART_BASE_MIN_POINTS = 300;
const HISTORY_CHART_BASE_DEFAULT_CAP = 25000;
const HISTORY_CHART_RESOLUTION_SCALE = 4.8;
const HISTORY_CHART_MIN_POINTS = Math.round(HISTORY_CHART_BASE_MIN_POINTS * HISTORY_CHART_RESOLUTION_SCALE);
const HISTORY_CHART_DEFAULT_CAP = Math.round(HISTORY_CHART_BASE_DEFAULT_CAP * HISTORY_CHART_RESOLUTION_SCALE);
const HISTORY_CHART_LINE_POINTS_PER_PLOT_PIXEL = 2;

const scaleHistoryChartPointCount = (points: number): number => {
    const normalized = Number(points);
    if (!Number.isFinite(normalized) || normalized <= 0) {
        throw new TypeError('points must be a positive number');
    }
    return Math.ceil(normalized * HISTORY_CHART_RESOLUTION_SCALE);
};

const resolveHistoryChartStorageCapacity = (apiPointCap: number, retentionMinutes: number | null, intervalMs: number, hardLimit: number): number => {
    if (!Number.isFinite(hardLimit) || hardLimit < 1) throw new TypeError('hardLimit must be a positive number');
    const retentionPoints = retentionMinutes !== null && Number.isFinite(retentionMinutes) && retentionMinutes > 0 && Number.isFinite(intervalMs) && intervalMs > 0 ? Math.ceil(minutesToMs(retentionMinutes) / intervalMs) : 0;
    const basePoints = Math.max(apiPointCap, retentionPoints, HISTORY_CHART_MIN_POINTS);
    return Math.min(Math.floor(hardLimit), scaleHistoryChartPointCount(basePoints));
};

const normalizeMonitoringIntervalMs = (monitoringIntervalMs: number): number => {
    const normalized = Math.round(Number(monitoringIntervalMs));
    if (!Number.isFinite(normalized) || normalized <= 0) {
        throw new TypeError('monitoringIntervalMs must be a positive number');
    }
    return normalized;
};

const resolveHistoryChartPointLimit = (config: HistoryChartPointBudgetConfig): number => {
    const candidates = [config.chartHardLimit, config.historyApiPointCap, config.maxHistoryPoints, HISTORY_CHART_DEFAULT_CAP].map((value) => Number(value)).filter((value): value is number => Number.isFinite(value) && value > 0);
    const limit = candidates.length ? Math.min(...candidates) : HISTORY_CHART_DEFAULT_CAP;
    return Math.max(1, Math.round(limit));
};

const clampHistoryChartPointCount = (config: HistoryChartPointBudgetConfig, value: number, min: number = HISTORY_CHART_MIN_POINTS, max: number = resolveHistoryChartPointLimit(config)): number => {
    if (!Number.isFinite(value) || value <= 0) {
        throw new TypeError('value must be a positive number');
    }
    const limit = clampNumber(Math.round(max), 1, resolveHistoryChartPointLimit(config));
    const minimum = clampNumber(Math.round(min), 1, limit);
    return clampNumber(Math.round(value), minimum, limit);
};

const resolveHistoryChartAlignedSampleBucketCount = (config: HistoryChartPointBudgetConfig, rangeMs: number): number => {
    const durationMs = Number(rangeMs);
    if (!Number.isFinite(durationMs) || durationMs <= 0) {
        throw new TypeError('rangeMs must be a positive number');
    }
    return Math.ceil(durationMs / normalizeMonitoringIntervalMs(config.monitoringIntervalMs)) + 1;
};

const resolveHistoryChartPlotWidthPx = (chart: Pick<HistoryChartInstance, 'view'> | null): number => (chart ? chart.view.getChartDimensions().chartWidth : 0);

const resolveHistoryChartDisplayPointFloor = (config: HistoryChartPointBudgetConfig): number => {
    const plotWidthPx = Number(config.plotWidthPx);
    if (!Number.isFinite(plotWidthPx) || plotWidthPx < 0) {
        throw new TypeError('plotWidthPx must be a non-negative number');
    }
    if (config.candlestickActive) return HISTORY_CHART_MIN_POINTS;
    return Math.max(HISTORY_CHART_MIN_POINTS, Math.ceil(plotWidthPx * HISTORY_CHART_LINE_POINTS_PER_PLOT_PIXEL));
};

const estimateHistoryChartIdealSpacing = (config: HistoryChartPointBudgetConfig, retentionMinutes: number): number => {
    const normalizedMinutes = Number(retentionMinutes);
    if (!Number.isFinite(normalizedMinutes) || normalizedMinutes <= 0) {
        throw new TypeError('retentionMinutes must be a positive number');
    }
    const cappedMinutes = config.maxRetentionMinutes !== null ? Math.min(normalizedMinutes, config.maxRetentionMinutes) : normalizedMinutes;
    const intervalMs = normalizeMonitoringIntervalMs(config.monitoringIntervalMs);
    const weight = cappedMinutes <= 60 ? 0.4 : cappedMinutes <= 360 ? 0.25 : cappedMinutes <= 1440 ? 0.18 : 0.12;
    const baseMs = Math.round(minutesToMs((cappedMinutes * weight) / Math.log10(cappedMinutes + 10)));
    const capMs = Math.max(intervalMs * 3, Math.round(minutesToMs(cappedMinutes ** 0.85)));
    return clampNumber(baseMs, Math.max(intervalMs * 2, intervalMs * Math.cbrt(cappedMinutes), intervalMs), capMs);
};

const computeHistoryChartPointBudget = (config: HistoryChartPointBudgetConfig, rangeMs: number): number => {
    const durationMs = Number(rangeMs);
    if (!Number.isFinite(durationMs) || durationMs <= 0) {
        throw new TypeError('rangeMs must be a positive number');
    }
    const retentionMinutes = msToMinutes(durationMs);
    const intervalMs = normalizeMonitoringIntervalMs(config.monitoringIntervalMs);
    const spacingMs = Math.max(intervalMs, estimateHistoryChartIdealSpacing(config, retentionMinutes));
    const spacedPoints = Math.ceil(durationMs / spacingMs);
    let pointBudget = spacedPoints;
    if (config.candlestickActive) {
        const intervalMinutes = Number(config.candlestickIntervalMinutes);
        if (!Number.isFinite(intervalMinutes) || intervalMinutes <= 0) {
            throw new TypeError('candlestickIntervalMinutes must be a positive number');
        }
        pointBudget = Math.max(pointBudget, Math.ceil(retentionMinutes / intervalMinutes) * 4);
    }
    const sampleBucketCount = resolveHistoryChartAlignedSampleBucketCount(config, durationMs);
    return clampHistoryChartPointCount(config, scaleHistoryChartPointCount(pointBudget), Math.min(resolveHistoryChartDisplayPointFloor(config), sampleBucketCount), sampleBucketCount);
};

export { HISTORY_CHART_DEFAULT_CAP, HISTORY_CHART_MIN_POINTS, clampHistoryChartPointCount, computeHistoryChartPointBudget, resolveHistoryChartPlotWidthPx, resolveHistoryChartPointLimit, resolveHistoryChartStorageCapacity, scaleHistoryChartPointCount };
export type { HistoryChartPointBudgetConfig };
