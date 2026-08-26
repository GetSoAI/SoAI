/* SoAI - Frontend live token-rate metric projection [frontend/assets/ts/features/metrics/liveTokenRates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber } from '@core/typeGuards.ts';
import type { Metrics } from '@features/metrics/metricsSnapshot.ts';

const resolveMetricsCurrentTokenRateOrNull = (metrics: Metrics): number | null => {
    const currentRate = metrics.tokenRates?.total?.effectiveRate;
    return isFiniteNumber(currentRate) && currentRate >= 0 ? currentRate : null;
};

const resolveMetricsCurrentTokenRate = (metrics: Metrics): number => {
    return resolveMetricsCurrentTokenRateOrNull(metrics) ?? 0;
};

export { resolveMetricsCurrentTokenRate, resolveMetricsCurrentTokenRateOrNull };
