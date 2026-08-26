/* SoAI - Shared compact numeric display primitive [frontend/assets/ts/core/primitives/compactNumber.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatInvariantCompactNumber, formatInvariantNumber } from '@core/localization/public.ts';

const formatCompactNumber = (value: number): string => {
    if (Math.abs(value) >= 1e3) return formatInvariantCompactNumber(value);
    return formatInvariantNumber(Math.round(value));
};

export { formatCompactNumber };
