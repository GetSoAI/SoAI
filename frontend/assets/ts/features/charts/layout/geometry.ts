/* SoAI - Charts feature geometry [frontend/assets/ts/features/charts/layout/geometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartDimensions, RenderGeometry, TimeWindow } from '@features/charts/rendering/renderingModels.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import type { ComponentOptionsRecord } from '@core/BaseComponent.ts';
import type { ChartOptions } from '@features/charts/chartTypes.ts';
import type { SlotMetrics } from '@features/charts/component/chartComponentTypes.ts';

const { isFinite: isFin } = Number;
const { min, max, abs } = Math;

type NumericIndexable = { length: number; [index: number]: number };

const MIN_CONTENT_INSET = 8;
const MAX_CONTENT_INSET_RATIO = 0.2;
const CONTENT_INSET_BAR_RATIO = 0.55;

const resolveContentInset = (width: number, pixelsPerBar: number): number => {
    const dynamicInset = isFin(pixelsPerBar) ? pixelsPerBar * CONTENT_INSET_BAR_RATIO : 0;
    return min(width / 2, max(MIN_CONTENT_INSET, min(max(0, width * MAX_CONTENT_INSET_RATIO), dynamicInset || MIN_CONTENT_INSET)));
};

interface RenderGeometryState {
    options: ComponentOptionsRecord<ChartOptions>;
    chartOptions: { maxDataPoints: number };
    visibleRange: { start: number; displayCount: number };
    pan: { offset: number };
    dataLength: number;
    timestamps: NumericIndexable;
}

interface RenderGeometryOperations {
    getChartDimensions: () => ChartDimensions;
    getEffectiveDataLength: () => number;
    getPixelsPerBar: () => number | null;
    getSlotMetrics: () => SlotMetrics;
    getMaxOffsetForMetrics: (metrics?: SlotMetrics | null) => number;
    getVisibleTimeWindow: () => TimeWindow | null;
}

const getRenderGeometry = (state: RenderGeometryState, operations: RenderGeometryOperations, dims?: ChartDimensions): RenderGeometry => {
    const actualDims = dims || operations.getChartDimensions();
    const { chartWidth: chartWidthValue, left } = actualDims;
    const chartWidth = Number(chartWidthValue) || 0;
    const { start = 0, displayCount: displayCountValue = 0 } = state.visibleRange;
    const totalSlots = max(1, Number(displayCountValue) || 0);
    const slotSpan = max(0, totalSlots - 1);
    const availableCount = max(0, operations.getEffectiveDataLength() - start);
    const visibleCount = availableCount > 0 ? max(1, min(availableCount, totalSlots)) : 0;
    const span = max(0, visibleCount - 1);
    const baseGeom = { span, chartWidth, visibleCount, baseLeft: left, nearTail: false };

    if (chartWidth <= 0)
        return {
            ...baseGeom,
            spacing: 0,
            originX: left,
            effectiveWidth: 0,
            rightBoundary: left,
            appliedMarginSlots: 0,
            timeWindow: null
        };

    const pixelsPerBar = operations.getPixelsPerBar() ?? 0;
    const contentInset = resolveContentInset(chartWidth, pixelsPerBar);
    const usableWidth = max(1, chartWidth - contentInset * 2);
    const metrics = operations.getSlotMetrics();
    const marginSlots = max(0, Number(metrics?.marginSlots) || 0);
    const nearTail = abs(state.pan.offset - operations.getMaxOffsetForMetrics(metrics)) < 1e-2;

    const ratioCap = slotSpan <= 2 ? 0.08 : slotSpan <= 4 ? 0.1 : slotSpan <= 8 ? 0.12 : slotSpan <= 15 ? 0.14 : slotSpan <= 30 ? 0.18 : slotSpan <= 60 ? 0.22 : slotSpan <= 120 ? 0.28 : 0.35;
    const optionRatio = readRuntimeFiniteNumberOrFallbackValue(state.options['maxRightMarginRatio'], null);
    const ratioLimit = max(0, min(ratioCap, optionRatio !== null ? min(0.45, optionRatio) : ratioCap));
    const baseSpacing = slotSpan > 0 ? usableWidth / slotSpan : usableWidth;

    let marginPixels = 0;
    if (nearTail && marginSlots > 0) {
        const maxPxValue = readRuntimeFiniteNumberOrFallbackValue(state.options['maxRightMarginPx'], null);
        const maxPx = maxPxValue !== null && maxPxValue > 0 ? maxPxValue : Infinity;
        marginPixels = min(usableWidth, maxPx, usableWidth * ratioLimit, slotSpan > 0 ? baseSpacing * min(marginSlots, slotSpan) : usableWidth);
    }

    const effectiveWidth = max(1, usableWidth - marginPixels);
    const spacing = span > 0 ? effectiveWidth / span : min(effectiveWidth, pixelsPerBar || effectiveWidth);
    const originBase = left + contentInset;

    return {
        ...baseGeom,
        baseLeft: originBase,
        spacing,
        effectiveWidth,
        rightBoundary: originBase + effectiveWidth,
        appliedMarginSlots: slotSpan > 0 && baseSpacing > 0 ? min(marginSlots, marginPixels / baseSpacing) : marginSlots,
        nearTail,
        originX: span > 0 ? originBase : originBase + effectiveWidth / 2,
        timeWindow: operations.getVisibleTimeWindow()
    };
};

const getXForVisibleIndex = (state: RenderGeometryState, index: number, displayCount: number, originX: number, spacing: number, geometry: RenderGeometry, dims: ChartDimensions): number => {
    const dataIndex = state.visibleRange.start + index;
    const baseLeft = geometry?.['baseLeft'] ?? dims['left'] ?? 0;
    const effectiveWidth = geometry?.['effectiveWidth'] ?? dims['chartWidth'] ?? 0;
    const timeWindow = geometry?.['timeWindow'];

    if (isFin(dataIndex) && dataIndex < state.dataLength && timeWindow && isFin(timeWindow['startTs']) && isFin(timeWindow['span']) && timeWindow['span'] > 0 && effectiveWidth > 0) {
        const ts = state.timestamps?.[dataIndex];
        if (ts !== undefined && isFin(ts)) {
            return baseLeft + ((ts - timeWindow['startTs']) / timeWindow['span']) * effectiveWidth;
        }
    }
    if (geometry?.['visibleCount'] <= 1) return originX;
    if (displayCount > 1) return originX + spacing * index;
    if (geometry['nearTail'] && geometry['effectiveWidth'] > 0) return geometry['rightBoundary'] ?? dims['left'] + geometry['effectiveWidth'];
    return isFin(geometry?.['originX']) ? geometry['originX'] : dims['left'] + dims['chartWidth'] / 2;
};

export { getRenderGeometry, getXForVisibleIndex };
export type { RenderGeometryOperations, RenderGeometryState };
