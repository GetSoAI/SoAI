/* SoAI - Charts feature state validation [frontend/assets/ts/features/charts/component/state/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isBoolean, isObject, isString } from '@core/typeGuards.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import type { ComponentOptionsRecord } from '@core/BaseComponent.ts';
import type { ChartOptions } from '@features/charts/chartTypes.ts';
import type { ChartStorageService } from '@features/charts/component/state/types.ts';

const isChartStorageService = <T>(value: T): value is T & ChartStorageService => isObject(value) && hasFunctionProperty(value, 'getChartColorMode') && hasFunctionProperty(value, 'getChartStaticColor');

const requireChartStorageService = (): ChartStorageService => {
    const candidate = resolveKernelService('core.storage');
    if (!isChartStorageService(candidate)) {
        throw new Error('ChartComponent requires core.storage.getChartColorMode/getChartStaticColor');
    }
    return candidate;
};

const isChartOptionsRecord = (value: ComponentOptionsRecord<ChartOptions>): value is ChartOptions => {
    const chartType = value['chartType'];
    const colors = value['colors'];
    const autoScale = value['autoScale'];
    const scaleType = value['scaleType'];

    if (!isString(chartType) || !chartType.trim()) return false;
    if (!isObject(colors)) return false;
    if (!isBoolean(autoScale)) return false;
    if (!isString(scaleType) || !scaleType.trim()) return false;

    return true;
};

export { isChartOptionsRecord, isChartStorageService, requireChartStorageService };
