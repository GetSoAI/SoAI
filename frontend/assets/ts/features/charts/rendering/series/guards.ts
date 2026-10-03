/* SoAI - Charts feature series validation [frontend/assets/ts/features/charts/rendering/series/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { VisiblePointsWithBuffers } from '@features/charts/renderingTypes.ts';
import type { VisiblePointsCacheType } from '@features/charts/rendering/series/types.ts';

const hasVisiblePointBuffers = (points: VisiblePointsCacheType): points is VisiblePointsWithBuffers => points.x instanceof Float64Array && points.y instanceof Float64Array && points.value instanceof Float64Array && points.valid instanceof Uint8Array && points.index instanceof Uint32Array;

const isPlottedValue = (value: number | null | undefined, logarithmic: boolean): value is number => typeof value === 'number' && Number.isFinite(value) && (!logarithmic || value > 0);

const isPlottedOhlc = (open: number | null | undefined, high: number | null | undefined, low: number | null | undefined, close: number | null | undefined, logarithmic: boolean): boolean => isPlottedValue(open, logarithmic) && isPlottedValue(high, logarithmic) && isPlottedValue(low, logarithmic) && isPlottedValue(close, logarithmic);

export { hasVisiblePointBuffers, isPlottedOhlc, isPlottedValue };
