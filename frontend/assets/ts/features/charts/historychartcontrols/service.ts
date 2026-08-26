/* SoAI - Charts feature history chart controls service [frontend/assets/ts/features/charts/historychartcontrols/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import { resolveCandlestickIntervalMs, resolveCandlestickSelection, resolveTimeRangeSelection } from '@features/charts/historychartcontrols/actions.ts';
import { requireChartRuntime } from '@features/charts/historychartcontrols/guards.ts';
import type { CandlestickSelectionOptions, ChartDataTransformsApi, HistoryChartControlsManagerConfig, HistoryChartRuntimeContract, ResolveCandlestickIntervalMsOptions, SyncCandlestickControlsOptions, SyncTimeRangeControlsOptions, TimeRangeOptions } from '@features/charts/historychartcontrols/types.ts';
import type { CandlestickSelection, TimeRangeSelection } from '@features/charts/controlsTypes.ts';

class HistoryChartControlsManager {
    readonly #chartRuntime: HistoryChartRuntimeContract;

    constructor({ chartRuntime }: HistoryChartControlsManagerConfig = {}) {
        this.#chartRuntime = requireChartRuntime(chartRuntime);
    }

    async syncTimeRangeControls({ retentionMinutes, baseOptions, selectedMinutes, onSelection }: SyncTimeRangeControlsOptions = {}): Promise<TimeRangeSelection> {
        const selection = await resolveTimeRangeSelection({
            chartRuntime: this.#chartRuntime,
            retentionMinutes,
            baseOptions,
            selectedMinutes
        });

        if (isFunction(onSelection)) {
            onSelection(selection);
        }

        return selection;
    }

    async syncCandlestickControls({ timeRangeMinutes, baseIntervals, supportedIntervalsMs, selectedIntervalMinutes, pointBudget, monitoringIntervalMs, onSelection }: SyncCandlestickControlsOptions = {}): Promise<CandlestickSelection> {
        const selection = await resolveCandlestickSelection({
            chartRuntime: this.#chartRuntime,
            timeRangeMinutes,
            baseIntervals,
            supportedIntervalsMs,
            selectedIntervalMinutes,
            pointBudget,
            monitoringIntervalMs
        });

        if (isFunction(onSelection)) {
            onSelection(selection);
        }

        return selection;
    }

    resolveCandlestickIntervalMs({ metadataIntervalMs, lastResolvedIntervalMs, requestedIntervalMinutes, supportedHistoryIntervalsMs, monitoringIntervalMs }: ResolveCandlestickIntervalMsOptions = {}): number {
        return resolveCandlestickIntervalMs({
            chartRuntime: this.#chartRuntime,
            metadataIntervalMs,
            lastResolvedIntervalMs,
            requestedIntervalMinutes,
            supportedHistoryIntervalsMs,
            monitoringIntervalMs
        });
    }
}

export { HistoryChartControlsManager };
export type { CandlestickSelectionOptions, ChartDataTransformsApi, HistoryChartControlsManagerConfig, HistoryChartRuntimeContract, ResolveCandlestickIntervalMsOptions, SyncCandlestickControlsOptions, SyncTimeRangeControlsOptions, TimeRangeOptions };
