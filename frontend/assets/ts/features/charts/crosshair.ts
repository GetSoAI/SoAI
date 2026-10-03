/* SoAI - Charts feature crosshair [frontend/assets/ts/features/charts/crosshair.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { CrosshairUpdatePayload } from '@features/charts/types.ts';
import { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
import { resolveVisibleSegmentIndexRange } from '@features/charts/component/data/visibleRange.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';
import { isMissingSampleInterval } from '@features/charts/rendering/series/sampleGaps.ts';
import { timeToX, xToTime } from '@features/charts/viewport/timeViewport.ts';

const isOverYAxis = (chart: ChartInteractionScene, xCoordinate: number, yCoordinate: number): boolean => {
    const { top, right, chartHeight } = chart.viewport.getChartDimensions();
    return xCoordinate >= right && yCoordinate >= top && yCoordinate <= top + chartHeight;
};

const isOverXAxis = (chart: ChartInteractionScene, xCoordinate: number, yCoordinate: number): boolean => {
    const { top, left, right, chartHeight, height } = chart.viewport.getChartDimensions();
    const axisTop = top + chartHeight;
    return xCoordinate >= left && xCoordinate <= right && yCoordinate >= axisTop && yCoordinate <= height;
};

const isOverChartArea = (chart: ChartInteractionScene, xCoordinate: number, yCoordinate: number): boolean => {
    const { top, left, right, chartHeight } = chart.viewport.getChartDimensions();
    return xCoordinate >= left && xCoordinate <= right && yCoordinate >= top && yCoordinate <= top + chartHeight;
};

const findNearestValidIndex = (chart: ChartInteractionScene, startIndex: number, rangeStart: number, rangeEnd: number): number => {
    for (let offset = 0; offset <= Math.max(startIndex - rangeStart, rangeEnd - 1 - startIndex); offset++) {
        const leftValue = startIndex - offset;
        if (leftValue >= rangeStart && Number.isFinite(chart.data.closeValue(leftValue))) return leftValue;
        const redChannel = startIndex + offset;
        if (redChannel < rangeEnd && Number.isFinite(chart.data.closeValue(redChannel))) return redChannel;
    }
    return -1;
};

const resolveRawIndex = (chart: ChartInteractionScene, targetTs: number): number => {
    const rightIndex = chart.data.findFirstTimestamp(targetTs);
    const leftIndex = chart.data.findLastTimestamp(targetTs);
    if (rightIndex === -1 || leftIndex === -1 || rightIndex === leftIndex) return rightIndex !== -1 ? rightIndex : leftIndex;
    const leftTs = chart.data.timestamps[leftIndex] ?? Number.NaN;
    const rightTs = chart.data.timestamps[rightIndex] ?? Number.NaN;
    return Number.isFinite(leftTs) && Number.isFinite(rightTs) && rightTs !== leftTs ? leftIndex + clampNumber((targetTs - leftTs) / (rightTs - leftTs), 0, 1) : rightIndex;
};

const applyCrosshairAt = (chart: ChartInteractionScene, mouseX: number): boolean => {
    const dims = chart.viewport.getChartDimensions();
    const viewport = chart.geometry.valueViewport();
    const ch = viewport ? viewport.height : dims.chartHeight;
    const top = viewport ? viewport.top : dims.top;
    const visibleRange = chart.viewportState.visibleRange;
    const geometry = chart.geometry.renderGeometry(dims);
    if (!geometry || chart.data.dataLength === 0) {
        hideCrosshair(chart);
        return false;
    }
    const rawChartType = chart.configuration.options.chartType;
    const chartType = typeof rawChartType === 'string' ? rawChartType : '';
    const wantsOhlc = chart.data.isOhlcType(chartType || undefined) || isOhlcChartType(chartType);
    const useDiscrete = chart.configuration.options.enableMagnetMode || !!(wantsOhlc ? chart.data.renderableOhlc() : null);
    const indexRange = useDiscrete ? { from: visibleRange.start, to: visibleRange.end } : resolveVisibleSegmentIndexRange(visibleRange, chart.data.dataLength);
    const { from: start, to: rangeEnd } = indexRange;
    if (rangeEnd <= start) {
        hideCrosshair(chart);
        return false;
    }
    const rawIndex = resolveRawIndex(chart, xToTime(geometry, clampNumber(mouseX, dims.left, dims.right)));
    if (!Number.isFinite(rawIndex) || rawIndex < 0) return false;

    const clampedRaw = clampNumber(rawIndex, start, rangeEnd - 1);

    let update: CrosshairUpdatePayload;
    let gap = false;
    if (useDiscrete) {
        const nearest = findNearestValidIndex(chart, Math.round(clampedRaw), start, rangeEnd);
        if (nearest === -1) return false;
        const nearestValue = chart.data.closeValue(nearest);
        const nearestTimestamp = chart.data.timestamps[nearest];
        update = {
            x: timeToX(geometry, nearestTimestamp ?? Number.NaN),
            dataIndex: nearest,
            rawIndex: nearest,
            value: nearestValue !== undefined ? nearestValue : null,
            timestamp: nearestTimestamp !== undefined ? nearestTimestamp : null,
            open: null,
            high: null,
            low: null,
            close: null
        };
    } else {
        const { value, timestamp } = chart.data.interpolate(clampedRaw, start, rangeEnd);
        if (!Number.isFinite(value) || timestamp === null) return false;
        const leftIndex = Math.floor(clampedRaw);
        gap = clampedRaw > leftIndex && isMissingSampleInterval(chart.data.timestamps[leftIndex] ?? Number.NaN, chart.data.timestamps[leftIndex + 1] ?? Number.NaN, chart.configuration.options.expectedSampleIntervalMs);
        update = {
            x: timeToX(geometry, timestamp),
            dataIndex: Math.round(clampedRaw),
            rawIndex: clampedRaw,
            value,
            timestamp,
            open: null,
            high: null,
            low: null,
            close: null
        };
    }

    if (chart.configuration.options.scaleType === 'logarithmic') {
        if (!update.value || !(update.value > 0)) return false;
        if (chart.data.hasOhlc() && update.dataIndex !== null) {
            const ohlc = chart.data.ohlcAt(clampNumber(update.dataIndex, 0, chart.data.dataLength - 1), chart.data.ohlcScratch);
            const ohlcOpen = ohlc.open;
            const ohlcHigh = ohlc.high;
            const ohlcLow = ohlc.low;
            const ohlcClose = ohlc.close;
            if (!(ohlcOpen && ohlcOpen > 0 && ohlcHigh && ohlcHigh > 0 && ohlcLow && ohlcLow > 0 && ohlcClose && ohlcClose > 0)) return false;
        }
    }

    if (chart.data.hasOhlc()) {
        chart.data.ohlcAt(clampNumber(update.dataIndex, 0, chart.data.dataLength - 1), update);
    }

    if (Array.isArray(chart.data.datasets) && update.dataIndex !== null) {
        const datasetValues: Record<string, number> = {};
        for (const dataset of chart.data.datasets) {
            if (!dataset?.name || !dataset?.values) continue;
            const value = dataset.values[update.dataIndex];
            if (value !== undefined && Number.isFinite(value)) datasetValues[dataset.name] = value;
        }
        if (Object.keys(datasetValues).length) {
            update.datasetValues = datasetValues;
        }
    }

    const ohlcOpen = typeof update['open'] === 'number' ? update['open'] : null;
    const ohlcHigh = typeof update['high'] === 'number' ? update['high'] : null;
    const ohlcLow = typeof update['low'] === 'number' ? update['low'] : null;
    const ohlcClose = typeof update['close'] === 'number' ? update['close'] : null;

    chart.interaction.crosshair = {
        visible: true,
        x: update.x,
        y: chart.presentation.valueToPixel(update.value ?? 0, ch, top),
        dataIndex: update.dataIndex,
        rawIndex: update.rawIndex,
        value: update.value,
        timestamp: update.timestamp,
        open: ohlcOpen,
        high: ohlcHigh,
        low: ohlcLow,
        close: ohlcClose,
        datasetValues: update.datasetValues ?? null,
        gap
    };
    chart.effects.emit('datapointHover', { ...chart.interaction.crosshair });
    return true;
};

const updateCrosshair = (chart: ChartInteractionScene, mouseX: number): void => {
    chart.interaction.pointer.hoverX = mouseX;
    if (applyCrosshairAt(chart, mouseX)) chart.effects.requestRedraw();
};

const refreshCrosshair = (chart: ChartInteractionScene): void => {
    const hoverX = chart.interaction.pointer.hoverX;
    if (hoverX === null || !chart.interaction.crosshair.visible) return;
    if (applyCrosshairAt(chart, hoverX)) chart.effects.requestRedraw({ interaction: true });
};

const hideCrosshair = (chart: ChartInteractionScene): void => {
    chart.interaction.pointer.hoverX = null;
    if (!chart.interaction.crosshair.visible) return;
    Object.assign(chart.interaction.crosshair, { visible: false, open: null, high: null, low: null, close: null, gap: false });
    chart.effects.requestRedraw();
};

export { hideCrosshair, isOverChartArea, isOverXAxis, isOverYAxis, refreshCrosshair, updateCrosshair };
