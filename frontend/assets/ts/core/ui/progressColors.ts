/* SoAI - Continuous progress color selection [frontend/assets/ts/core/ui/progressColors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampPercent } from '@core/primitives/clampNumber.ts';

type ProgressColorDirection = 'completion' | 'usage';

const resolveProgressColor = (percent: number, direction: ProgressColorDirection = 'completion'): string => {
    const normalized = Math.round(clampPercent(percent) * 10) / 10;
    const position = ((direction === 'usage' ? 100 - normalized : normalized) * 3) / 100;
    const interval = Math.min(2, Math.floor(position));
    const weight = Number(((position - interval) * 100).toFixed(6));
    const start = interval === 0 ? '--status-red' : interval === 1 ? '--status-orange' : '--status-yellow';
    const end = interval === 0 ? '--status-orange' : interval === 1 ? '--status-yellow' : '--status-green';
    if (weight === 0) return `var(${start})`;
    if (weight === 100) return `var(${end})`;
    const remaining = Number((100 - weight).toFixed(6));
    return `color-mix(in srgb, var(${start}) ${remaining}%, var(${end}) ${weight}%)`;
};

export { resolveProgressColor };
export type { ProgressColorDirection };
