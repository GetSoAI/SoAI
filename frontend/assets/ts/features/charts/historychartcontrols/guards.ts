/* SoAI - Charts feature history chart controls validation [frontend/assets/ts/features/charts/historychartcontrols/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isArray, isObject } from '@core/typeGuards.ts';
import type { ChartDataTransformsApi } from '@features/charts/controlsTypes.ts';
import type { HistoryChartRuntimeContract } from '@features/charts/historyChartContracts.ts';

const isFiniteNumberArray = <T>(value: T): value is T & number[] => {
    if (!isArray(value)) {
        return false;
    }
    return value.every((entry) => typeof entry === 'number' && Number.isFinite(entry));
};

const isChartDataTransforms = <T>(value: T): value is T & ChartDataTransformsApi => {
    if (!isObject(value)) {
        return false;
    }
    if (!('constants' in value)) {
        return false;
    }
    const constants = value.constants;
    if (!isObject(constants)) {
        return false;
    }
    if (!('DEFAULT_TIME_RANGES' in constants) || !isFiniteNumberArray(constants.DEFAULT_TIME_RANGES)) {
        return false;
    }
    if (!('DEFAULT_CANDLE_INTERVALS' in constants) || !isFiniteNumberArray(constants.DEFAULT_CANDLE_INTERVALS)) {
        return false;
    }
    return hasFunctionProperty(value, 'buildTimeRangeSelection') && hasFunctionProperty(value, 'buildCandlestickIntervalSelection') && hasFunctionProperty(value, 'formatTimeRangeMinutes') && hasFunctionProperty(value, 'resolveSupportedIntervalMs');
};

const requireChartRuntime = (chartRuntime: HistoryChartRuntimeContract | undefined): HistoryChartRuntimeContract => {
    if (!chartRuntime) {
        throw new Error('History chart controls manager requires a chart runtime instance');
    }
    return chartRuntime;
};

const resolveChartDataTransforms = async (chartRuntime: HistoryChartRuntimeContract): Promise<ChartDataTransformsApi> => {
    await chartRuntime.ensureModules();
    return resolveCachedChartDataTransforms(chartRuntime);
};

const resolveCachedChartDataTransforms = (chartRuntime: HistoryChartRuntimeContract): ChartDataTransformsApi => {
    const modules = chartRuntime.getCachedModules();
    if (!modules) {
        throw new Error('Chart data utilities must be initialized before using history controls');
    }
    const dataTransformsValue = modules.data;
    if (!isChartDataTransforms(dataTransformsValue)) {
        throw new Error('Chart data utilities must provide default history ranges and candlestick intervals');
    }
    return dataTransformsValue;
};

export { requireChartRuntime, resolveChartDataTransforms, resolveCachedChartDataTransforms };
