/* SoAI - Charts feature history chart contracts [frontend/assets/ts/features/charts/historyChartContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartModules } from '@features/charts/chartModules.ts';
import type { ChartOptions } from '@features/charts/chartTypes.ts';
import type { FilterOptionsInput } from '@features/charts/chartfilters/filterOptionTypes.ts';
import type { CandlestickSelection, TimeRangeSelection } from '@features/charts/controlsTypes.ts';
import type { ChartPointInput } from '@features/charts/data/chartPointTypes.ts';

type HistoryChartDataTransformsModule = ChartModules['data'];
type HistoryChartOhlcModule = ChartModules['ohlc'];
type HistoryChartDefaultsConstants = HistoryChartDataTransformsModule['constants'];
type ChartFactory = (container: HTMLElement | string | null, options?: Partial<ChartOptions>) => HistoryChartInstance;

interface HistoryChartInstance {
    settings: {
        readonly snapshot: Readonly<ChartOptions>;
        update(options: Partial<ChartOptions>): void;
        setChartType(type: string): void;
        setMetricName(name: string | null): void;
        setValueFormatter(formatter: (value: number) => string): void;
    };
    data: {
        replace(data: ReadonlyArray<ChartPointInput>, options?: { preserveView?: boolean; assumeSorted?: boolean }): void;
        prepend(points: ReadonlyArray<ChartPointInput>): void;
        appendPoint(point: ChartPointInput): void;
        updateCurrentBar(point: ChartPointInput): void;
    };
    view: {
        readonly status: Readonly<{ isAnimating: boolean; isDragging: boolean; isAtTail: boolean }>;
        fitTimeRange(minutes: number, options?: { align?: string | undefined }): boolean;
        alignToLatest(): void;
        resize(): boolean;
    };
    lifecycle: {
        initialize(options?: { signal?: AbortSignal }): Promise<void>;
        destroy(): Promise<void>;
    };
}

interface HistoryChartDefaults {
    timeRanges: number[];
    candleIntervals: number[];
    constants: HistoryChartDefaultsConstants;
}

interface ResolvePointBudgetOptions {
    chart?: Pick<HistoryChartInstance, 'settings'> | undefined;
    maxHistoryPoints?: number | undefined;
    historyApiPointCap?: number | undefined;
}

interface InitializeChartOptions {
    container?: HTMLElement;
    chartType?: string;
    options?: Partial<ChartOptions>;
    onRequestHistoricalData?: ((timestamp: number) => void | Promise<void>) | null;
    signal?: AbortSignal | undefined;
}

interface LoadChartDefaultsOptions {
    onDefaults?: ((defaults: HistoryChartDefaults) => void) | undefined;
}

interface HistoryChartRuntimeContract {
    ensureModules(): Promise<ChartModules>;
    getCachedModules(): ChartModules | null;
    getDataTransforms(): HistoryChartDataTransformsModule;
    getOhlc(): HistoryChartOhlcModule;
    getDefaults(): HistoryChartDefaults;
    loadDefaults(options?: LoadChartDefaultsOptions): Promise<ChartModules>;
    resolvePointBudget(options: ResolvePointBudgetOptions): number;
    initializeChart(options?: InitializeChartOptions): Promise<HistoryChartInstance>;
    reset(): void;
}

type HistoryChartFormattingRuntimeContract = Pick<HistoryChartRuntimeContract, 'getCachedModules'>;

interface HistoryChartFiltersContract {
    setTimeRangeOptions(options: FilterOptionsInput): HistoryChartFiltersContract;
    setCandleIntervals(intervals: FilterOptionsInput): HistoryChartFiltersContract;
    setValue(type: string, value: string | number | null, notify?: boolean): HistoryChartFiltersContract;
    updateChartTypeVisibility(chartType: string): void;
    dispose(): void;
}

interface HistoryChartControlsContract {
    syncTimeRangeControls(options?: { retentionMinutes?: number | undefined; baseOptions?: number[] | undefined; selectedMinutes?: number | undefined }): Promise<TimeRangeSelection>;
    syncCandlestickControls(options?: { timeRangeMinutes?: number | undefined; baseIntervals?: number[] | undefined; supportedIntervalsMs?: number[] | undefined; selectedIntervalMinutes?: number | undefined; pointBudget?: number | undefined; monitoringIntervalMs?: number | undefined }): Promise<CandlestickSelection>;
    resolveCandlestickIntervalMs(options?: { metadataIntervalMs?: number | undefined; lastResolvedIntervalMs?: number | undefined; requestedIntervalMinutes?: number | undefined; supportedHistoryIntervalsMs?: number[] | undefined; monitoringIntervalMs?: number | undefined }): number;
}

interface ApplyHistoryChartDefaultsOptions {
    defaults?:
        | {
              timeRanges?: number[] | undefined;
              candleIntervals?: number[] | undefined;
          }
        | undefined;
    chartFilters: HistoryChartFiltersContract | null;
    currentTimeRanges?: readonly number[] | null | undefined;
    currentCandleIntervals?: readonly number[] | null | undefined;
    setTimeRanges: (timeRanges: number[]) => void;
    setCandleIntervals: (candleIntervals: number[]) => void;
}

interface SyncHistoryTimeRangeOptions {
    chartFilters: HistoryChartFiltersContract | null;
    historyControlsManager: HistoryChartControlsContract;
    retentionMinutes?: number | null | undefined;
    baseOptions?: readonly number[] | null | undefined;
    selectedMinutes: number;
    onSelection: (selection: TimeRangeSelection) => void;
    isCurrent?: (() => boolean) | undefined;
}

interface SyncHistoryCandlestickOptions {
    chartFilters: HistoryChartFiltersContract | null;
    historyControlsManager: HistoryChartControlsContract;
    chartType: string;
    timeRangeMinutes: number;
    baseIntervals?: readonly number[] | null | undefined;
    supportedIntervalsMs?: readonly number[] | null | undefined;
    selectedIntervalMinutes: number;
    pointBudget: number;
    monitoringIntervalMs: number;
    onSelection: (selection: CandlestickSelection) => void;
    isCurrent?: (() => boolean) | undefined;
}

type HistoryChartFilterOptionsInput = FilterOptionsInput;

export type { ApplyHistoryChartDefaultsOptions, ChartFactory, HistoryChartControlsContract, HistoryChartDataTransformsModule, HistoryChartDefaults, HistoryChartDefaultsConstants, HistoryChartFilterOptionsInput, HistoryChartFiltersContract, HistoryChartFormattingRuntimeContract, HistoryChartInstance, HistoryChartOhlcModule, HistoryChartRuntimeContract, InitializeChartOptions, LoadChartDefaultsOptions, ResolvePointBudgetOptions, SyncHistoryCandlestickOptions, SyncHistoryTimeRangeOptions };
