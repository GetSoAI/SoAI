/* SoAI - Charts feature history chart runtime [frontend/assets/ts/features/charts/HistoryChartRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DEFAULT_CHART_PADDING, DEFAULT_PRIMARY_BOTTOM_AXIS_PADDING, HISTORY_CHART_MIN_HEIGHT } from '@core/charts/constants.ts';
import { isFunction, isInstanceOf, isString } from '@core/typeGuards.ts';
import { chartModulesAccess, type ChartModules, type ChartModulesAccess } from '@features/charts/chartModules.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { ChartFactory, HistoryChartDataTransformsModule, HistoryChartDefaults, HistoryChartInstance, HistoryChartOhlcModule, HistoryChartRuntimeContract, InitializeChartOptions, LoadChartDefaultsOptions, ResolvePointBudgetOptions } from '@features/charts/historyChartContracts.ts';

interface HistoryChartRuntimeConfig {
    modules?: ChartModulesAccess;
}

const cloneNumberArray = (value: readonly number[], label: string): number[] => {
    if (!Array.isArray(value) || value.length === 0) {
        throw new Error(`Chart runtime requires at least one ${label}`);
    }
    const normalized: number[] = [];
    for (const entry of value) {
        if (typeof entry !== 'number' || !Number.isFinite(entry)) {
            throw new Error(`Chart runtime requires numeric ${label}`);
        }
        normalized.push(entry);
    }
    return normalized;
};

class HistoryChartRuntime implements HistoryChartRuntimeContract {
    readonly #modulesAccess: ChartModulesAccess;
    #modules: ChartModules | null = null;
    #loading: Promise<ChartModules> | null = null;
    #generation = 0;

    constructor({ modules = chartModulesAccess }: HistoryChartRuntimeConfig = {}) {
        this.#modulesAccess = modules;
    }

    async ensureModules(): Promise<ChartModules> {
        if (this.#modules) {
            return this.#modules;
        }
        if (!this.#loading) {
            const generation = this.#generation;
            let loading!: Promise<ChartModules>;
            loading = this.#modulesAccess
                .ensure()
                .then((modules) => {
                    if (generation !== this.#generation) {
                        throw new LifecycleCancellationError('History chart runtime reset during module loading', 'history-chart-runtime-reset');
                    }
                    this.#modules = modules;
                    return modules;
                })
                .finally(() => {
                    if (this.#loading === loading) this.#loading = null;
                });
            this.#loading = loading;
        }
        return this.#loading;
    }

    getCachedModules(): ChartModules | null {
        return this.#modules;
    }

    getModulesSync(): ChartModules {
        if (this.#modules) {
            return this.#modules;
        }
        const modules = this.#modulesAccess.getSync();
        this.#modules = modules;
        return modules;
    }

    getChartFactory(): ChartFactory {
        const factory = this.getModulesSync().createSession;
        if (!isFunction(factory)) {
            throw new Error('Chart runtime factory unavailable');
        }
        return factory;
    }

    getDataTransforms(): HistoryChartDataTransformsModule {
        const dataTransforms = this.getModulesSync().data;
        if (!dataTransforms) {
            throw new Error('Chart runtime data transforms unavailable');
        }
        return dataTransforms;
    }

    getOhlc(): HistoryChartOhlcModule {
        const ohlc = this.getModulesSync().ohlc;
        if (!ohlc) {
            throw new Error('Chart runtime OHLC utilities unavailable');
        }
        return ohlc;
    }

    getDefaults(): HistoryChartDefaults {
        const constants = this.getDataTransforms().constants;
        return {
            timeRanges: cloneNumberArray(constants.DEFAULT_TIME_RANGES, 'default time range'),
            candleIntervals: cloneNumberArray(constants.DEFAULT_CANDLE_INTERVALS, 'default candle interval'),
            constants
        };
    }

    async loadDefaults({ onDefaults }: LoadChartDefaultsOptions = {}): Promise<ChartModules> {
        const modules = await this.ensureModules();
        if (onDefaults) {
            onDefaults(this.getDefaults());
        }
        return modules;
    }

    resolvePointBudget({ chart, maxHistoryPoints, historyApiPointCap }: ResolvePointBudgetOptions): number {
        const candidates = [chart?.settings.snapshot.maxDataPoints, maxHistoryPoints, historyApiPointCap].map((value) => (typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null)).filter((value): value is number => value !== null);
        if (candidates.length === 0) {
            throw new Error('History chart requires at least one positive point budget candidate');
        }
        return Math.min(...candidates);
    }

    async initializeChart({ container, chartType, options = {}, onRequestHistoricalData, signal }: InitializeChartOptions = {}): Promise<HistoryChartInstance> {
        if (!isInstanceOf(container, HTMLElement)) {
            throw new Error('History chart container element is required');
        }
        if (!isString(chartType) || !chartType.trim()) {
            throw new Error('History chart type is required');
        }
        throwIfAborted(signal);
        await this.ensureModules();
        throwIfAborted(signal);
        const historicalDataRequest = isFunction(onRequestHistoricalData) ? onRequestHistoricalData : (options.onRequestHistoricalData ?? null);
        const chart = this.getChartFactory()(container, {
            autoScale: true,
            enableCrosshair: true,
            enableInertialPanning: true,
            minHeight: HISTORY_CHART_MIN_HEIGHT,
            padding: { ...DEFAULT_CHART_PADDING },
            bottomAxisPadding: DEFAULT_PRIMARY_BOTTOM_AXIS_PADDING,
            rightMarginBars: 0,
            chartType,
            ...options,
            onRequestHistoricalData: historicalDataRequest
        });
        try {
            await chart.lifecycle.initialize(signal ? { signal } : {});
            throwIfAborted(signal);
            return chart;
        } catch (error) {
            try {
                await chart.lifecycle.destroy();
            } catch (cleanupError) {
                errorHandler.error('HistoryChartRuntime', 'Chart initialization rollback failed', ensureError(cleanupError));
            }
            throw error;
        }
    }

    reset(): void {
        this.#generation += 1;
        this.#modulesAccess.reset();
        this.#loading = null;
        this.#modules = null;
    }
}

export { HistoryChartRuntime };
export type { ChartFactory, HistoryChartDataTransformsModule, HistoryChartDefaults, HistoryChartInstance, HistoryChartOhlcModule, HistoryChartRuntimeConfig, HistoryChartRuntimeContract, InitializeChartOptions, LoadChartDefaultsOptions, ResolvePointBudgetOptions };
