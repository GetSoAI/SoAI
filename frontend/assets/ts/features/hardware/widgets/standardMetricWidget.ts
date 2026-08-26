/* SoAI - Hardware feature standard metric widget [frontend/assets/ts/features/hardware/widgets/standardMetricWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { isArray, isFiniteNumber } from '@core/typeGuards.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { isNonEmptyFiniteNumberArrayValue } from '@core/types/runtimeCollectionGuards.ts';
import { formatHardwareNumber, formatMemoryUsage, formatPowerWatts } from '@features/hardware/Formatters.ts';
import type { HardwareWidgetDataPoint, HardwareWidgetHistoryData, UnitConfig } from '@features/hardware/widgets/contracts.ts';
import { WIDGET_CONSTANTS } from '@features/hardware/widgets/constants.ts';
import { updateTemperatureDisplay } from '@features/hardware/widgets/displayValues.ts';
import type { MetricKeySet } from '@features/hardware/widgets/metricKeysRegistry.ts';
import { resolveNumericMetric } from '@features/hardware/widgets/metricValues.ts';

interface StandardWidgetData {
    utilization?: number | undefined;
    memoryUsedMb?: number | undefined;
    memoryTotalMb?: number | undefined;
    powerWatts?: number | undefined;
    powerLimit?: number | undefined;
    temperature?: number | undefined;
    telemetryAvailable?: boolean | undefined;
}

interface StandardWidgetDisplayArguments {
    elements: Record<string, HTMLElement>;
    units: Record<string, UnitConfig>;
    data: StandardWidgetData | null;
    memoryMetricId: string;
}

interface StandardWidgetHistoryArguments {
    historyData: HardwareWidgetHistoryData;
    metricKeys: MetricKeySet;
    memoryMetricId: string;
    missingTimestampPolicy: 'skip' | 'throw';
}

const unavailableLabel = (): string => i18n.t('common.notAvailableShort');

const normalizeStandardWidgetData = (source: StandardWidgetData | null | undefined): StandardWidgetData | null => {
    if (!source) {
        return null;
    }
    const getNumber = (key: keyof StandardWidgetData): number | undefined => {
        const value = source[key];
        return isFiniteNumber(value) ? value : undefined;
    };

    return {
        utilization: getNumber('utilization'),
        memoryUsedMb: getNumber('memoryUsedMb'),
        memoryTotalMb: getNumber('memoryTotalMb'),
        powerWatts: getNumber('powerWatts'),
        powerLimit: getNumber('powerLimit'),
        temperature: getNumber('temperature'),
        telemetryAvailable: source.telemetryAvailable === false ? false : true
    };
};

const resolveMemoryPercent = (data: StandardWidgetData): number => {
    const memoryTotal = isFiniteNumber(data.memoryTotalMb) ? data.memoryTotalMb : null;
    const memoryUsed = isFiniteNumber(data.memoryUsedMb) ? data.memoryUsedMb : null;
    return memoryTotal !== null && memoryTotal > 0 && memoryUsed !== null ? (memoryUsed / memoryTotal) * 100 : 0;
};

const resolvePowerPercent = (data: StandardWidgetData): number => {
    const powerWatts = isFiniteNumber(data.powerWatts) ? data.powerWatts : null;
    const powerLimit = isFiniteNumber(data.powerLimit) ? data.powerLimit : null;
    return powerWatts !== null && powerLimit !== null && powerLimit > 0 ? (powerWatts / powerLimit) * 100 : 0;
};

const resolveTemperaturePercent = (data: StandardWidgetData): number => {
    return isFiniteNumber(data.temperature) && data.temperature > 0 ? (data.temperature / WIDGET_CONSTANTS.TEMPERATURE_MAX_SCALE) * 100 : 0;
};

const createStandardWidgetDataPoint = (data: StandardWidgetData, memoryMetricId: string, timestamp: number): HardwareWidgetDataPoint => {
    return {
        core: data.utilization ?? 0,
        [memoryMetricId]: resolveMemoryPercent(data),
        power: resolvePowerPercent(data),
        temperature: resolveTemperaturePercent(data),
        timestamp
    };
};

const transformStandardWidgetHistoryData = (inputArguments: StandardWidgetHistoryArguments): HardwareWidgetDataPoint[] => {
    if (!isJsonObject(inputArguments.historyData)) {
        return [];
    }

    const timestampsRaw = inputArguments.historyData.timestampsMs;
    if (!isNonEmptyFiniteNumberArrayValue(timestampsRaw)) {
        return [];
    }
    const timestamps = timestampsRaw;

    const dataArrayRaw = inputArguments.historyData['data'];
    if (!isArray(dataArrayRaw) || !dataArrayRaw.length) {
        return [];
    }
    const dataArray = dataArrayRaw;
    const limit = Math.min(timestamps.length, dataArray.length);
    const points: HardwareWidgetDataPoint[] = [];

    for (let index = 0; index < limit; index += 1) {
        const row = dataArray[index];
        if (!isJsonObject(row)) {
            continue;
        }

        const timestamp = timestamps[index];
        if (timestamp === undefined) {
            if (inputArguments.missingTimestampPolicy === 'throw') {
                throw new Error(`Hardware widget history timestamp missing at index ${index}`);
            }
            continue;
        }

        const utilization = resolveNumericMetric(row, inputArguments.metricKeys.utilization) ?? 0;
        const memoryPercent = resolveNumericMetric(row, inputArguments.metricKeys.memory) ?? 0;
        const powerWatts = resolveNumericMetric(row, inputArguments.metricKeys.power);
        const powerLimit = resolveNumericMetric(row, inputArguments.metricKeys.powerLimit);
        const temperature = resolveNumericMetric(row, inputArguments.metricKeys.temperature) ?? 0;
        const powerPercent = isFiniteNumber(powerWatts) && isFiniteNumber(powerLimit) && powerLimit > 0 ? (powerWatts / powerLimit) * 100 : 0;

        points.push({
            core: utilization,
            [inputArguments.memoryMetricId]: memoryPercent,
            power: powerPercent,
            temperature: temperature > 0 ? (temperature / WIDGET_CONSTANTS.TEMPERATURE_MAX_SCALE) * 100 : 0,
            timestamp
        });
    }

    return points;
};

const updateStandardWidgetDisplayValues = (inputArguments: StandardWidgetDisplayArguments): void => {
    const coreElement = inputArguments.elements['core'];
    if (coreElement) {
        if (inputArguments.data?.telemetryAvailable === false) {
            dom.setText(coreElement, unavailableLabel());
        } else {
            const utilization = inputArguments.data?.utilization ?? 0;
            dom.setText(coreElement, `${formatHardwareNumber(utilization, 0)}%`);
        }
    }

    const memoryElement = inputArguments.elements[inputArguments.memoryMetricId];
    const memoryUnit = inputArguments.units[inputArguments.memoryMetricId];
    if (inputArguments.data?.telemetryAvailable === false && memoryElement) {
        dom.setText(memoryElement, unavailableLabel());
    } else if (inputArguments.data && memoryElement && memoryUnit && isFiniteNumber(inputArguments.data.memoryUsedMb) && isFiniteNumber(inputArguments.data.memoryTotalMb) && inputArguments.data.memoryTotalMb > 0) {
        dom.setText(memoryElement, formatMemoryUsage(inputArguments.data.memoryUsedMb, inputArguments.data.memoryTotalMb, memoryUnit.current));
    } else if (memoryElement) {
        dom.setText(memoryElement, '');
    }

    const powerElement = inputArguments.elements['power'];
    const powerUnit = inputArguments.units['power'];
    if (inputArguments.data?.telemetryAvailable === false && powerElement) {
        dom.setText(powerElement, unavailableLabel());
    } else if (inputArguments.data && powerElement && powerUnit && isFiniteNumber(inputArguments.data.powerWatts) && inputArguments.data.powerWatts > 0) {
        dom.setText(powerElement, formatPowerWatts(inputArguments.data.powerWatts, powerUnit.current));
    } else if (powerElement) {
        dom.setText(powerElement, '');
    }

    const temperatureElement = inputArguments.elements['temperature'];
    const temperatureUnit = inputArguments.units['temperature'];
    if (temperatureElement && temperatureUnit) {
        if (inputArguments.data?.telemetryAvailable === false) {
            dom.setText(temperatureElement, unavailableLabel());
        } else {
            const rawTemperature = inputArguments.data && isFiniteNumber(inputArguments.data.temperature) && inputArguments.data.temperature > 0 ? inputArguments.data.temperature : null;
            updateTemperatureDisplay(temperatureElement, rawTemperature, temperatureUnit.current);
        }
    }
};

const hasStandardPowerMetric = (data: StandardWidgetData | null): boolean => isFiniteNumber(data?.powerWatts) && data.powerWatts > 0;

const hasStandardTemperatureMetric = (data: StandardWidgetData | null): boolean => isFiniteNumber(data?.temperature) && data.temperature > 0;

export { createStandardWidgetDataPoint, hasStandardPowerMetric, hasStandardTemperatureMetric, normalizeStandardWidgetData, transformStandardWidgetHistoryData, updateStandardWidgetDisplayValues };
export type { StandardWidgetData };
