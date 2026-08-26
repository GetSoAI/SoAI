/* SoAI - Metrics page layout constants [frontend/assets/ts/pages/metrics/rendering/layout/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MovableGridSettings } from '@core/routing/pages/movablesections/types.ts';

const METRICS_GRID_SETTINGS = Object.freeze<MovableGridSettings>({
    columns: 2,
    baseCellHeight: 380,
    dragThreshold: 5,
    dragScale: 1.05,
    responsive: {
        type: 'breakpoints',
        breakpoints: [{ maxWidth: 1200, columns: 1 }]
    }
});

export { METRICS_GRID_SETTINGS };
