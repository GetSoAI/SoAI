/* SoAI - Charts feature interpolation [frontend/assets/ts/features/charts/component/data/interpolation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isFin } from '@features/charts/component/chartComponentStatics.ts';

interface InterpolationHost {
    timestamps: Float64Array;
    getCloseValue: (index: number) => number | undefined;
}

const findValidIndexBackward = (chart: InterpolationHost, start: number, limit: number): number => {
    for (let index = start; index >= limit; index--) if (isFin(chart.getCloseValue(index))) return index;
    return -1;
};

const findValidIndexForward = (chart: InterpolationHost, start: number, upper: number): number => {
    for (let index = start; index <= upper; index++) if (isFin(chart.getCloseValue(index))) return index;
    return -1;
};

const resolveInterpolationAnchors = (chart: InterpolationHost, raw: number, start: number, end: number): { leftIndex: number; rightIndex: number } | null => {
    const floorIndex = clampNumber(Math.floor(raw), start, end - 1);
    const ceilIndex = clampNumber(Math.ceil(raw), start, end - 1);
    if (floorIndex === ceilIndex) return isFin(chart.getCloseValue(floorIndex)) ? { leftIndex: floorIndex, rightIndex: floorIndex } : null;
    const left = findValidIndexBackward(chart, floorIndex, start);
    const right = findValidIndexForward(chart, ceilIndex, end - 1);
    if (left === -1 && right === -1) return null;
    return { leftIndex: left === -1 ? right : left, rightIndex: right === -1 ? left : right };
};

const interpolate = (chart: InterpolationHost, raw: number, start: number, end: number): { value: number | null; timestamp: number | null } => {
    const anchors = resolveInterpolationAnchors(chart, raw, start, end);
    if (!anchors) return { value: null, timestamp: null };
    const { leftIndex, rightIndex } = anchors;
    const leftValue = chart.getCloseValue(leftIndex) ?? Number.NaN;
    const leftTimestamp = chart.timestamps[leftIndex] ?? Number.NaN;
    if (leftIndex === rightIndex) return { value: leftValue, timestamp: leftTimestamp };
    const rightValue = chart.getCloseValue(rightIndex) ?? Number.NaN;
    const rightTimestamp = chart.timestamps[rightIndex] ?? Number.NaN;
    const currentTime = rightIndex > leftIndex ? clampNumber((raw - leftIndex) / (rightIndex - leftIndex), 0, 1) : 0;
    return {
        value: leftValue + (rightValue - leftValue) * currentTime,
        timestamp: leftTimestamp + (rightTimestamp - leftTimestamp) * currentTime
    };
};

export { findValidIndexBackward, findValidIndexForward, interpolate, resolveInterpolationAnchors };
