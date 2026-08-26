/* SoAI - Charts feature scale bounds [frontend/assets/ts/features/charts/scales/scaleBounds.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber } from '@core/typeGuards.ts';
import type { ChartOptions } from '@features/charts/chartTypes.ts';
import type { Scale } from '@features/charts/component/chartComponentTypes.ts';

interface ScaleBoundsHost {
    chartOptions: ChartOptions;
    scale: Scale;
    yAxisMinRange: number;
    getChartDimensions: () => { chartHeight: number };
    requestRedraw: (request?: { data?: boolean; interaction?: boolean }) => void;
}

const enforceScaleBounds = (host: ScaleBoundsHost, { preserveRange = false } = {}): void => {
    const bounds = host.chartOptions.scaleBounds;
    if (!bounds || !isFiniteNumber(host.scale.min) || !isFiniteNumber(host.scale.max)) return;
    const { min: boundsMin, max: boundsMax } = bounds;
    const isLog = host.chartOptions.scaleType === 'logarithmic';
    const minRange = Math.max(host.yAxisMinRange || 1e-6, isLog ? 1e-6 : 0);
    let min = host.scale.min;
    let max = host.scale.max;
    if (min > max) [min, max] = [max, min];
    const currentRange = Math.max(minRange, max - min);
    if (preserveRange) {
        let targetRange = currentRange;
        if (boundsMin !== undefined && boundsMax !== undefined) targetRange = Math.min(targetRange, Math.max(minRange, boundsMax - boundsMin));
        if (boundsMax !== undefined && max > boundsMax) {
            const delta = max - boundsMax;
            min -= delta;
            max -= delta;
        }
        if (boundsMin !== undefined && min < boundsMin) {
            const delta = boundsMin - min;
            min += delta;
            max += delta;
        }
        if (boundsMin !== undefined && boundsMax !== undefined && max - min > boundsMax - boundsMin) {
            min = boundsMin;
            max = boundsMax;
        } else if (max - min < targetRange) {
            const center = (max + min) / 2;
            min = center - targetRange / 2;
            max = center + targetRange / 2;
            if (boundsMin !== undefined && min < boundsMin) {
                min = boundsMin;
                max = min + targetRange;
            }
            if (boundsMax !== undefined && max > boundsMax) {
                max = boundsMax;
                min = max - targetRange;
            }
        }
    } else {
        if (boundsMin !== undefined) min = Math.max(min, boundsMin);
        if (boundsMax !== undefined) max = Math.min(max, boundsMax);
    }
    if (isLog) {
        if (min <= 0) min = boundsMin && boundsMin > 0 ? boundsMin : 1e-9;
        if (max <= min) max = min + Math.max(minRange, 1e-6);
    }
    if (max - min < minRange) {
        const mid = (max + min) / 2;
        min = mid - minRange / 2;
        max = mid + minRange / 2;
    }
    if (boundsMin !== undefined && min < boundsMin) {
        min = boundsMin;
        max = Math.max(min + minRange, max);
    }
    if (boundsMax !== undefined && max > boundsMax) {
        max = boundsMax;
        min = Math.min(max - minRange, min);
    }
    if (boundsMin !== undefined && min < boundsMin) min = boundsMin;
    if (boundsMin !== undefined && boundsMax !== undefined) {
        min = Math.max(boundsMin, min);
        max = Math.min(boundsMax, max);
        if (max - min < minRange) {
            if (boundsMax - boundsMin >= minRange) {
                min = Math.max(boundsMin, boundsMax - minRange);
                max = min + minRange;
            } else {
                min = boundsMin;
                max = boundsMax;
            }
        }
    }
    host.scale.min = min;
    host.scale.max = max;
};

const panVertical = (host: ScaleBoundsHost, deltaY: number): boolean => {
    if (!isFiniteNumber(deltaY) || deltaY === 0 || host.scale.auto || !isFiniteNumber(host.scale.min) || !isFiniteNumber(host.scale.max)) return false;
    const scaleMin = host.scale.min;
    const scaleMax = host.scale.max;
    const { chartHeight } = host.getChartDimensions();
    if (!chartHeight) return false;
    if (host.chartOptions.scaleType === 'logarithmic') {
        if (!(scaleMin > 0 && scaleMax > 0)) return false;
        const lMin = Math.log10(scaleMin);
        const lMax = Math.log10(scaleMax);
        const range = Math.max(host.yAxisMinRange, lMax - lMin, 1e-6);
        const shift = deltaY * (range / Math.max(1, chartHeight));
        if (!isFiniteNumber(shift) || shift === 0) return false;
        let nextMin = lMin + shift;
        let nextMax = lMax + shift;
        if (nextMax - nextMin < range) {
            const center = (nextMax + nextMin) / 2;
            nextMin = center - range / 2;
            nextMax = center + range / 2;
        }
        host.scale.min = 10 ** nextMin;
        host.scale.max = 10 ** nextMax;
    } else {
        const shift = deltaY * (Math.max(host.yAxisMinRange, scaleMax - scaleMin) / Math.max(1, chartHeight));
        if (!isFiniteNumber(shift) || shift === 0) return false;
        host.scale.min = scaleMin + shift;
        host.scale.max = scaleMax + shift;
    }
    enforceScaleBounds(host, { preserveRange: true });
    host.requestRedraw({ data: true, interaction: true });
    return true;
};

export { enforceScaleBounds, panVertical };
