/* SoAI - Hardware page boundary contracts [frontend/assets/ts/pages/hardware/contracts/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DisposableResource } from '@core/resourcetracker/types.ts';
import type { HistoryChartControlsContract, HistoryChartDataTransformsModule, HistoryChartFiltersContract, HistoryChartInstance, HistoryChartOhlcModule, HistoryChartRuntimeContract } from '@features/charts/public.ts';

type HistoryControlsManagerInstance = HistoryChartControlsContract;
type ChartDataTransformsContract = HistoryChartDataTransformsModule;
type ChartFiltersInstance = HistoryChartFiltersContract;
type ChartInstance = HistoryChartInstance;
type ChartOhlcContract = HistoryChartOhlcModule;
type HistoryChartRuntimeInstance = HistoryChartRuntimeContract;

type ResourcesInterface = {
    untrack?(handle: DisposableResource): void;
};

export type { ChartFiltersInstance, ChartInstance, ChartDataTransformsContract, ChartOhlcContract, HistoryChartRuntimeInstance, HistoryControlsManagerInstance, ResourcesInterface };
