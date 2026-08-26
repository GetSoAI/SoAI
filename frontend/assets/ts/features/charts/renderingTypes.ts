/* SoAI - Charts feature rendering types [frontend/assets/ts/features/charts/renderingTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { VisiblePointsCache } from '@features/charts/chartTypes.ts';

export interface VisiblePointsWithBuffers extends VisiblePointsCache {
    x: Float64Array;
    y: Float64Array;
    value: Float64Array;
    valid: Uint8Array;
    index: Uint32Array;
    length: number;
}
