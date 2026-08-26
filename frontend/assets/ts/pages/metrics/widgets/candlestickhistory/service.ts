/* SoAI - Metrics page candlestick history service [frontend/assets/ts/pages/metrics/widgets/candlestickhistory/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { serializeSystemMetricsHistoryRequest } from '@core/api/contracts/systemMetricsRequestContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isArray, isFiniteNumber, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import type { HistoryChartOhlcModule } from '@features/charts/public.ts';
import { buildHistoryWindow, computeCandlestickPointBudget, resolveHistoryIntervalMs } from '@pages/metrics/mappers/metricsHistoryMapping.ts';
import { applyCandlestickHistory, applyCandlestickMetadata, trimCandlestickData } from '@pages/metrics/widgets/candlestickhistory/effects.ts';
import type { CandlestickHistoryContext } from '@pages/metrics/widgets/candlestickhistory/types.ts';

const fetchCandlestickHistory = async (context: CandlestickHistoryContext, chartOhlc: HistoryChartOhlcModule, { resetView = false, beforeTimestampMs = null }: { resetView?: boolean; beforeTimestampMs?: number | null } = {}): Promise<boolean> =>
    context.query.runWithBoundary('metrics:fetchCandlestickHistory', async () => {
        const metricKey = context.query.getMetricHistoryKey();
        if (!metricKey) {
            return false;
        }
        const catalogEntry = context.query.getCatalogEntry(metricKey);
        if (!catalogEntry) {
            throw new Error(`Missing metricsCatalog entry for: ${metricKey}`);
        }
        const aggregations = isArray(catalogEntry.aggregations) ? catalogEntry.aggregations : [];
        const aggregation = context.query.getMetricHistoryOhlcAggregation();
        if (!context.limits.supportsOhlc || !aggregations.includes(aggregation)) {
            return false;
        }
        const requestingOlder = isFiniteNumber(beforeTimestampMs);
        if (requestingOlder && context.state.candlestickHistoryExhausted) {
            return false;
        }
        const intervalMs = context.query.getEffectiveCandlestickIntervalMs();
        const timeWindow = buildHistoryWindow({
            beforeTimestampMs,
            intervalMs,
            expand: requestingOlder ? 1.5 : 1,
            timeRangeMinutes: context.limits.timeRange,
            maxRetentionMinutes: context.limits.maxRetentionMinutes
        });
        if (!timeWindow || timeWindow.startTsMs >= timeWindow.endTsMs) {
            return false;
        }
        const { startTsMs, endTsMs, rangeMs } = timeWindow;
        const resolvedIntervalMs = resolveHistoryIntervalMs({
            startTsMs,
            endTsMs,
            requestedIntervalMs: intervalMs,
            pointBudget: context.limits.pointBudget,
            supportedIntervalsMs: context.limits.supportedHistoryIntervalsMs
        });
        if (requestingOlder && startTsMs === 0) {
            context.state.candlestickHistoryExhausted = true;
        }

        const query = serializeSystemMetricsHistoryRequest({
            metricKey: metricKey,
            startTsMs: startTsMs,
            endTsMs: endTsMs,
            aggregation,
            points: computeCandlestickPointBudget({
                rangeMs,
                intervalMs: resolvedIntervalMs,
                pointBudget: context.limits.pointBudget
            }),
            intervalMs: resolvedIntervalMs > 0 ? resolvedIntervalMs : undefined
        });

        const signature = JSON.stringify(query);
        if (context.query.isRequestActive() && context.query.getRequestSignature() === signature) {
            return false;
        }
        context.query.setRequestSignature(signature);
        context.query.setRequestActive(true);

        const previousEarliest = context.state.candlestickData[0]?.timestamp ?? null;
        let response: JsonObject | null = null;
        try {
            response = await requestWebSocketSnapshotRecord('system.metrics.history', query);
        } finally {
            if (context.query.getRequestSignature() === signature) {
                context.query.setRequestActive(false);
            }
        }

        if (context.query.getRequestSignature() !== signature) {
            return false;
        }
        if (!isObject(response)) {
            throw new TypeError('metrics candlestick history response must be an object');
        }
        applyCandlestickHistory(context, chartOhlc, response, { resetView });
        if (requestingOlder) {
            const newEarliest = context.state.candlestickData[0]?.timestamp ?? null;
            if (isNullOrUndefined(newEarliest) || (!isNullOrUndefined(previousEarliest) && newEarliest >= previousEarliest)) {
                context.state.candlestickHistoryExhausted = true;
            }
        }
        return true;
    });

export { applyCandlestickHistory, applyCandlestickMetadata, fetchCandlestickHistory, trimCandlestickData };
export type { CandlestickHistoryContext };
