/* SoAI - Charts feature crosshair [frontend/assets/ts/features/charts/crosshair.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { CrosshairUpdatePayload } from '@features/charts/types.ts';
import { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';

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

const updateCrosshair = (chart: ChartInteractionScene, mouseX: number): void => {
    const dims = chart.viewport.getChartDimensions();
    const { chartWidth, left } = dims;
    const viewport = chart.geometry.valueViewport();
    const ch = viewport ? viewport.height : dims.chartHeight;
    const top = viewport ? viewport.top : dims.top;
    const { displayCount: dc, offsetFraction: of, start } = chart.viewportState.visibleRange;

    if (chartWidth <= 0 || dc <= 0 || chart.data.dataLength === 0) return;

    const geo = chart.geometry.renderGeometry(dims);
    const span = Math.max(0, dc - 1);
    const rightBoundary = Number.isFinite(geo.rightBoundary) ? geo.rightBoundary : left + chartWidth;
    const clampedX = clampNumber(mouseX, left, rightBoundary);
    const spacing = Number.isFinite(geo.spacing) && geo.spacing > 0 ? geo.spacing : span > 0 ? chartWidth / Math.max(1, span) : chartWidth;
    const baseLeft = Number.isFinite(geo.baseLeft) ? geo.baseLeft : left;
    const originX = baseLeft - spacing * of;

    let rawIndex;
    const tw = geo.timeWindow ?? null;
    const effectiveWidth = Number.isFinite(geo.effectiveWidth) && geo.effectiveWidth > 0 ? geo.effectiveWidth : chartWidth;
    if (tw && Number.isFinite(tw.startTs) && Number.isFinite(tw.span) && tw.span > 0 && effectiveWidth > 0) {
        const rel = clampNumber((clampedX - baseLeft) / effectiveWidth, 0, 1);
        const targetTs = tw.startTs + rel * tw.span;
        const rIndex = chart.data.findFirstTimestamp(targetTs);
        const lIndex = chart.data.findLastTimestamp(targetTs);

        if (rIndex === -1 && lIndex === -1) return;
        if (rIndex !== -1 && lIndex !== -1 && rIndex !== lIndex) {
            const lt = chart.data.timestamps[lIndex];
            const rt = chart.data.timestamps[rIndex];
            if (lt !== undefined && rt !== undefined && Number.isFinite(lt) && Number.isFinite(rt) && rt !== lt) {
                rawIndex = lIndex + clampNumber((targetTs - lt) / (rt - lt), 0, 1);
            } else rawIndex = rIndex;
        } else rawIndex = rIndex !== -1 ? rIndex : lIndex;
    } else {
        rawIndex = span > 0 && spacing > 0 ? start + (clampedX - originX) / spacing : start;
    }

    const rangeEnd = Math.min(chart.data.dataLength, start + dc);
    if (!Number.isFinite(rawIndex) || rangeEnd <= start) return;

    const clampedRaw = clampNumber(rawIndex, start, rangeEnd - 1);
    const rawChartType = chart.configuration.options.chartType;
    const chartType = typeof rawChartType === 'string' ? rawChartType : '';
    const wantsOhlc = chart.data.isOhlcType(chartType || undefined) || isOhlcChartType(chartType);
    const useDiscrete = chart.configuration.options.enableMagnetMode || !!(wantsOhlc ? chart.data.renderableOhlc() : null);

    let update: CrosshairUpdatePayload;
    if (useDiscrete) {
        const nearest = findNearestValidIndex(chart, Math.round(clampedRaw), start, rangeEnd);
        if (nearest === -1) return;
        const nearestValue = chart.data.closeValue(nearest);
        const nearestTimestamp = chart.data.timestamps[nearest];
        update = {
            x: chart.geometry.xForVisibleIndex(nearest - start),
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
        if (!Number.isFinite(value)) return;
        update = {
            x: clampedX,
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
        if (!update.value || !(update.value > 0)) return;
        if (chart.data.hasOhlc() && update.dataIndex !== null) {
            const ohlc = chart.data.ohlcAt(clampNumber(update.dataIndex, 0, chart.data.dataLength - 1), chart.data.ohlcScratch);
            const ohlcOpen = ohlc.open;
            const ohlcHigh = ohlc.high;
            const ohlcLow = ohlc.low;
            const ohlcClose = ohlc.close;
            if (!(ohlcOpen && ohlcOpen > 0 && ohlcHigh && ohlcHigh > 0 && ohlcLow && ohlcLow > 0 && ohlcClose && ohlcClose > 0)) return;
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
        datasetValues: update.datasetValues ?? null
    };
    chart.effects.emit('datapointHover', { ...chart.interaction.crosshair });
    chart.effects.requestRedraw();
};

const hideCrosshair = (chart: ChartInteractionScene): void => {
    if (!chart.interaction.crosshair.visible) return;
    Object.assign(chart.interaction.crosshair, { visible: false, open: null, high: null, low: null, close: null });
    chart.effects.requestRedraw();
};

export { hideCrosshair, isOverChartArea, isOverXAxis, isOverYAxis, updateCrosshair };
