/* SoAI - Metrics page candlestick history service [frontend/assets/ts/pages/metrics/widgets/candlestickhistory/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemMetricsHistoryRequest } from '@core/api/contracts/systemMetricsRequestContracts.ts';
import { isArray } from '@core/typeGuards.ts';
import { resolveHistoryPagePoints, type HistoryPageWindow } from '@features/charts/public.ts';
import { buildHistoryWindow, computeCandlestickPointBudget, resolveHistoryIntervalMs } from '@pages/metrics/mappers/metricsHistoryMapping.ts';
import type { CandlestickHistoryContext } from '@pages/metrics/widgets/candlestickhistory/types.ts';

const resolveCandlestickHistoryRequest = (context: CandlestickHistoryContext, page: HistoryPageWindow | null): SystemMetricsHistoryRequest | null => {
    const metricKey = context.query.getMetricHistoryKey();
    if (!metricKey) {
        return null;
    }
    const catalogEntry = context.query.getCatalogEntry(metricKey);
    if (!catalogEntry) {
        throw new Error(`Missing metricsCatalog entry for: ${metricKey}`);
    }
    const aggregations = isArray(catalogEntry.aggregations) ? catalogEntry.aggregations : [];
    const aggregation = context.query.getMetricHistoryOhlcAggregation();
    if (!context.limits.supportsOhlc || !aggregations.includes(aggregation)) {
        return null;
    }
    const intervalMs = context.query.getEffectiveCandlestickIntervalMs();
    if (page) {
        return { metricKey, startTsMs: page.startTsMs, endTsMs: page.endTsMs, aggregation, points: resolveHistoryPagePoints(page, intervalMs), intervalMs };
    }
    const timeWindow = buildHistoryWindow({ timeRangeMinutes: context.limits.timeRange, maxRetentionMinutes: context.limits.maxRetentionMinutes });
    if (!timeWindow || timeWindow.startTsMs >= timeWindow.endTsMs) {
        return null;
    }
    const resolvedIntervalMs = resolveHistoryIntervalMs({
        startTsMs: timeWindow.startTsMs,
        endTsMs: timeWindow.endTsMs,
        requestedIntervalMs: intervalMs,
        pointBudget: context.limits.pointBudget,
        supportedIntervalsMs: context.limits.supportedHistoryIntervalsMs
    });
    return {
        metricKey,
        startTsMs: timeWindow.startTsMs,
        endTsMs: timeWindow.endTsMs,
        aggregation,
        points: computeCandlestickPointBudget({ rangeMs: timeWindow.rangeMs, intervalMs: resolvedIntervalMs, pointBudget: context.limits.pointBudget }),
        intervalMs: resolvedIntervalMs > 0 ? resolvedIntervalMs : undefined
    };
};

export { resolveCandlestickHistoryRequest };
