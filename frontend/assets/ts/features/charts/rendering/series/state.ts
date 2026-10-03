/* SoAI - Charts feature series state [frontend/assets/ts/features/charts/rendering/series/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveRenderIndexRange } from '@features/charts/component/data/visibleRange.ts';
import type { ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import { getValueViewport } from '@features/charts/rendering/axes.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import type { VisiblePointsWithBuffers } from '@features/charts/renderingTypes.ts';
import type { SeriesValueArray, VisiblePointsCacheType } from '@features/charts/rendering/series/types.ts';
import { timeToX } from '@features/charts/viewport/timeViewport.ts';

const isCacheCurrent = (cache: VisiblePointsCacheType, next: Omit<VisiblePointsCacheType, 'length'>): boolean => cache.series === next.series && cache.start === next.start && cache.end === next.end && cache.dataLength === next.dataLength && cache.scaleMin === next.scaleMin && cache.scaleMax === next.scaleMax && cache.chartHeight === next.chartHeight && cache.chartTop === next.chartTop && cache.plotLeft === next.plotLeft && cache.plotWidth === next.plotWidth && cache.rightEdgeTs === next.rightEdgeTs && cache.msPerPx === next.msPerPx;

const calculateVisiblePoints = (scene: ChartRenderingScene, values: SeriesValueArray, dataLength: number, dims: ChartDimensions, geometry: RenderGeometry): VisiblePointsCacheType => {
    const { top: chartTop, height: chartHeight } = getValueViewport(scene, dims);
    const length = Math.min(dataLength, values.length, scene.state.dataLength);
    const { from: start, to: end } = resolveRenderIndexRange(scene.state.visibleRange, length);
    const { min: scaleMin, max: scaleMax } = scene.state.scale;
    const next = { series: values, start, end, dataLength: length, scaleMin, scaleMax, chartHeight, chartTop, plotLeft: geometry.plotLeft, plotWidth: geometry.plotWidth, rightEdgeTs: geometry.rightEdgeTs, msPerPx: geometry.msPerPx };
    const cache = scene.state.visiblePointsCache;
    if (cache && isCacheCurrent(cache, next)) return cache;
    const target: VisiblePointsCacheType = Object.assign(cache ?? { length: 0 }, next, { length: 0 });
    scene.state.visiblePointsCache = target;
    if (end <= start || scaleMin === null || scaleMax === null || chartHeight <= 0) return target;

    const { x: xArr, y: yArr, value: valueArr, valid: validArr, index: indexArr } = scene.buffers.ensureRenderBufferCapacity(end - start);
    Object.assign(target, { x: xArr, y: yArr, value: valueArr, valid: validArr, index: indexArr });
    const timestamps = scene.state.timestamps;
    const isLog = scene.state.chartOptions.scaleType === 'logarithmic';
    let count = 0;
    for (let dataIndex = start; dataIndex < end; dataIndex++) {
        const value = values[dataIndex];
        const timestamp = timestamps[dataIndex];
        if (value === undefined || timestamp === undefined || !Number.isFinite(timestamp)) continue;
        const isValid = Number.isFinite(value) && (!isLog || value > 0);
        xArr[count] = timeToX(geometry, timestamp);
        indexArr[count] = dataIndex;
        valueArr[count] = value;
        yArr[count] = isValid ? scene.format.valueToPixel(value, chartHeight, chartTop) : 0;
        validArr[count] = isValid ? 1 : 0;
        count++;
    }
    target.length = count;
    return target;
};

const findLatestValidIndex = (points: VisiblePointsWithBuffers): number => {
    for (let index = points.length - 1; index >= 0; index--) {
        const validValue = points.valid[index];
        if (validValue !== undefined && validValue) return index;
    }
    return -1;
};

export { calculateVisiblePoints, findLatestValidIndex };
