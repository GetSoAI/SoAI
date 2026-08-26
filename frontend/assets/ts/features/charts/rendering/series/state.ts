/* SoAI - Charts feature series state [frontend/assets/ts/features/charts/rendering/series/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import { getRenderGeometry, getXForVisibleIndex } from '@features/charts/layout/geometry.ts';
import { getValueViewport } from '@features/charts/rendering/axes.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import type { VisiblePointsWithBuffers } from '@features/charts/renderingTypes.ts';
import type { SeriesValueArray, VisiblePointsCacheType } from '@features/charts/rendering/series/types.ts';

const { min, max, ceil } = Math;
const { isFinite: isFiniteNumber } = Number;

const calculateVisiblePoints = (scene: ChartRenderingScene, values: SeriesValueArray, dataLength: number, dims?: ChartDimensions, geometry?: RenderGeometry): VisiblePointsCacheType => {
    const actualDims = dims || scene.geometry.getChartDimensions();
    const actualGeometry = geometry || getRenderGeometry(scene.state, scene.geometry, actualDims);
    const chartWidthValue = actualDims.chartWidth;
    const chartWidth = Number(chartWidthValue) || 0;
    const valueViewport = getValueViewport(scene, actualDims);
    const top = valueViewport.top;
    const chartHeight = valueViewport.height;
    const { displayCount: displayCountValue, offsetFraction, start } = scene.state.visibleRange;
    const displayCount = Number(displayCountValue) || 0;
    const { min: scaleMin, max: scaleMax } = scene.state.scale;
    const { spacing: gSpacing, baseLeft: gLeft, originX: gOrigin, visibleCount: gVisibleCount, effectiveWidth: gEffectiveWidth, timeWindow } = actualGeometry;

    const spacing = gSpacing || (displayCount > 1 ? chartWidth / max(1, displayCount - 1) : chartWidth);
    const baseLeft = gLeft ?? actualDims.left;
    const origin = gOrigin ?? baseLeft;
    const visibleCount = max(1, gVisibleCount ?? min(displayCount, dataLength - start));
    const effectiveWidth = gEffectiveWidth ?? chartWidth;
    const timeStart = timeWindow?.startTs ?? null;
    const timeEnd = timeWindow?.endTs ?? null;
    const timeSpan = timeWindow?.span ?? null;

    const cache = scene.state.visiblePointsCache;
    if (cache && typeof cache === 'object' && cache.series === values && cache.start === start && cache.displayCount === displayCount && cache.offsetFraction === offsetFraction && cache.scaleMin === scaleMin && cache.scaleMax === scaleMax && cache.chartWidth === chartWidth && cache.chartHeight === chartHeight && cache.chartTop === top && cache.timeStart === timeStart && cache.timeEnd === timeEnd) {
        return cache;
    }

    const targetCache: VisiblePointsCacheType =
        cache ??
        (scene.state.visiblePointsCache = {
            series: values,
            start,
            displayCount,
            offsetFraction,
            dataLength,
            scaleMin,
            scaleMax,
            chartWidth,
            chartHeight,
            chartTop: top,
            spacing,
            baseLeft,
            originBase: origin,
            visibleCount,
            effectiveWidth,
            timeStart,
            timeEnd,
            timeSpan,
            length: 0
        });

    targetCache.series = values;
    targetCache.start = start;
    targetCache.displayCount = displayCount;
    targetCache.offsetFraction = offsetFraction;
    targetCache.dataLength = dataLength;
    targetCache.scaleMin = scaleMin;
    targetCache.scaleMax = scaleMax;
    targetCache.chartWidth = chartWidth;
    targetCache.chartHeight = chartHeight;
    targetCache.chartTop = top;
    targetCache.spacing = spacing;
    targetCache.baseLeft = baseLeft;
    targetCache.originBase = origin;
    targetCache.visibleCount = visibleCount;
    targetCache.effectiveWidth = effectiveWidth;
    targetCache.length = 0;
    targetCache.timeStart = timeStart;
    targetCache.timeEnd = timeEnd;
    targetCache.timeSpan = timeSpan;

    if (displayCount <= 0 || scaleMin === null || scaleMax === null || chartHeight <= 0 || chartWidth <= 0) return targetCache;

    const buffer = ceil(visibleCount * 0.1);
    const culledStart = max(0, start - buffer);
    const culledCount = max(0, min(dataLength, start + visibleCount + buffer) - culledStart);
    if (culledCount === 0) return targetCache;

    const { x: xArr, y: yArr, value: valueArr, valid: validArr, index: indexArr } = scene.buffers.ensureRenderBufferCapacity(culledCount);
    targetCache.x = xArr;
    targetCache.y = yArr;
    targetCache.value = valueArr;
    targetCache.valid = validArr;
    targetCache.index = indexArr;

    const originX = origin - spacing * offsetFraction;
    const useTime = timeWindow && isFiniteNumber(timeStart) && timeStart !== null && isFiniteNumber(timeSpan) && timeSpan !== null && timeSpan > 0 && effectiveWidth > 0;
    const timestamps = useTime ? scene.state.timestamps : null;
    const isLog = scene.state.chartOptions.scaleType === 'logarithmic';
    let len = 0;

    for (let index = 0; index < culledCount; index++) {
        const dataIndex = culledStart + index;
        const visIndex = dataIndex - start;
        if (visIndex < -buffer || visIndex >= displayCount + buffer) continue;

        const value = values[dataIndex];
        if (value === undefined) continue;
        const isValid = isFiniteNumber(value) && (!isLog || value > 0);

        let xCoordinate: number;
        if (useTime && timestamps && timeStart !== null && timeSpan !== null && timeSpan > 0) {
            const tsValue = timestamps[dataIndex];
            if (tsValue !== undefined && isFiniteNumber(tsValue)) {
                xCoordinate = baseLeft + ((tsValue - timeStart) / timeSpan) * effectiveWidth;
            } else {
                xCoordinate = getXForVisibleIndex(scene.state, visIndex, displayCount, originX, spacing, actualGeometry, actualDims);
            }
        } else {
            xCoordinate = getXForVisibleIndex(scene.state, visIndex, displayCount, originX, spacing, actualGeometry, actualDims);
        }

        xArr[len] = xCoordinate;
        indexArr[len] = dataIndex;
        valueArr[len] = value;
        yArr[len] = isValid ? scene.format.valueToPixel(value, chartHeight, top) : 0;
        validArr[len] = isValid ? 1 : 0;
        len++;
    }
    targetCache.length = len;
    return targetCache;
};

const findLatestValidIndex = (points: VisiblePointsWithBuffers): number => {
    for (let index = points.length - 1; index >= 0; index--) {
        const validValue = points.valid[index];
        if (validValue !== undefined && validValue) return index;
    }
    return -1;
};

export { calculateVisiblePoints, findLatestValidIndex };
