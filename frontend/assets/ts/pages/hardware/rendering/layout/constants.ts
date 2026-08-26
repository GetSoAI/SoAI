/* SoAI - Hardware page layout constants [frontend/assets/ts/pages/hardware/rendering/layout/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MovableGridSettings } from '@core/routing/pages/movablesections/types.ts';

const HARDWARE_GRID_SETTINGS = Object.freeze<MovableGridSettings>({
    columns: 3,
    baseCellHeight: 80,
    dragThreshold: 5,
    dragScale: 1.05,
    responsive: {
        type: 'breakpoints',
        breakpoints: [
            { maxWidth: 1200, columns: 1 },
            { maxWidth: 1600, columns: 2 }
        ]
    }
});

export { HARDWARE_GRID_SETTINGS };
