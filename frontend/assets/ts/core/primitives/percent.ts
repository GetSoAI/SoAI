/* SoAI - Shared percent formatting primitive [frontend/assets/ts/core/primitives/percent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatInvariantNumber } from '@core/localization/public.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

const formatPercent = (value: number, decimals: number = 1): string => {
    const numericValue = Number(value);
    if (!isFiniteNumber(numericValue)) throw new Error('Percent value must be numeric');
    return `${formatInvariantNumber(numericValue, { maximumFractionDigits: Math.max(0, decimals) })}%`;
};

const formatPercentFromFraction = (fraction: number, decimals: number = 1): string => {
    const numericFraction = Number(fraction);
    if (!isFiniteNumber(numericFraction)) throw new Error('Percent fraction must be numeric');
    return `${formatInvariantNumber(numericFraction * 100, { maximumFractionDigits: Math.max(0, decimals) })}%`;
};

export { formatPercent, formatPercentFromFraction };
