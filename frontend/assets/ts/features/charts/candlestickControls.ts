/* SoAI - Charts feature candlestick controls [frontend/assets/ts/features/charts/candlestickControls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import { normalizeChartTypeToken } from '@features/charts/chartTypeNormalization.ts';
import type { HistoryChartControlsContract, HistoryChartInstance } from '@features/charts/historyChartContracts.ts';

type ControlsManager = HistoryChartControlsContract;
type ChartInstance = HistoryChartInstance;

interface CandlestickIntervalOptions {
    metadataIntervalMs?: number | undefined;
    lastResolvedIntervalMs?: number | undefined;
    requestedIntervalMinutes?: number | undefined;
    supportedHistoryIntervalsMs?: number[] | undefined;
    monitoringIntervalMs?: number | undefined;
}

interface IsCandlestickModeActiveOptions {
    chartType?: string | undefined;
    chart?: ChartInstance | undefined;
}

interface ResolveCandlestickIntervalMsOptions extends CandlestickIntervalOptions {
    controlsManager?: ControlsManager;
}

const resolveChartType = (explicitType: string | undefined, chartInstance: ChartInstance | undefined): string | null => normalizeChartTypeToken(explicitType ?? chartInstance?.settings.snapshot.chartType ?? null);

export const isCandlestickModeActive = ({ chartType, chart }: IsCandlestickModeActiveOptions = {}): boolean => resolveChartType(chartType, chart) === 'candlestick';

export const resolveCandlestickIntervalMs = ({ controlsManager, metadataIntervalMs, lastResolvedIntervalMs, requestedIntervalMinutes, supportedHistoryIntervalsMs, monitoringIntervalMs }: ResolveCandlestickIntervalMsOptions = {}): number => {
    if (!isObject(controlsManager) || !isFunction(controlsManager.resolveCandlestickIntervalMs)) {
        throw new Error('Candlestick controls require a history controls manager');
    }
    return controlsManager.resolveCandlestickIntervalMs({
        metadataIntervalMs,
        lastResolvedIntervalMs,
        requestedIntervalMinutes,
        supportedHistoryIntervalsMs,
        monitoringIntervalMs
    });
};

export type { ChartInstance, ControlsManager, CandlestickIntervalOptions, IsCandlestickModeActiveOptions, ResolveCandlestickIntervalMsOptions };
