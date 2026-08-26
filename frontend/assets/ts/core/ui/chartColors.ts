/* SoAI - Shared UI chart colors [frontend/assets/ts/core/ui/chartColors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { getDocumentElement } from '@core/environment/public.ts';
import { toTrimmedLower } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';
import { computeHash } from '@core/primitives/hash.ts';

const CHART_COLOR_COUNT = 100;

type ChartColorMode = 'disabled' | 'static' | 'dynamic';

type ChartColorContextOption = {
    value: string;
    label?: string | undefined;
    getLabel?: (() => string) | undefined;
};

type ChartColorContextInput = {
    device: string;
    deviceOptions: ReadonlyArray<ChartColorContextOption>;
    metric: string;
    metricOptions: ReadonlyArray<ChartColorContextOption>;
};

type ChartColorContext = {
    device: string;
    deviceIndex: number;
    metric: string;
    metricIndex: number;
    subjectName: string;
};

const findOptionIndex = (options: ReadonlyArray<ChartColorContextOption>, selected: string): number => {
    for (let index = 0; index < options.length; index += 1) {
        if (options[index]?.value === selected) return index;
    }
    return -1;
};

const resolveOptionLabel = (option: ChartColorContextOption | null): string | null => {
    if (!option) return null;
    const raw = (() => {
        if (typeof option.label === 'string') return option.label;
        const getLabel = option.getLabel;
        if (typeof getLabel === 'function') return getLabel();
        return null;
    })();
    const normalized = typeof raw === 'string' ? raw.trim() : '';
    return normalized ? normalized : null;
};

const buildChartColorContext = (input: ChartColorContextInput): ChartColorContext => {
    const matchedDeviceIndex = findOptionIndex(input.deviceOptions, input.device);
    const matchedMetricIndex = findOptionIndex(input.metricOptions, input.metric);
    const deviceIndex = Math.max(0, matchedDeviceIndex);
    const metricIndex = Math.max(0, matchedMetricIndex);
    const deviceOption = matchedDeviceIndex >= 0 ? (input.deviceOptions[matchedDeviceIndex] ?? null) : null;
    const subjectName = resolveOptionLabel(deviceOption) || input.device;
    return {
        device: input.device,
        deviceIndex,
        metric: input.metric,
        metricIndex,
        subjectName
    };
};

const getChartColorIndex = (device: JsonValue | undefined, deviceIndex: JsonValue | undefined, metric: JsonValue | undefined, metricIndex: JsonValue | undefined): number => {
    const devicePart = toTrimmedLower(device) || '';
    const metricPart = toTrimmedLower(metric) || '';
    const deviceIndexPart = deviceIndex === null || deviceIndex === undefined ? '' : String(deviceIndex);
    const metricIndexPart = metricIndex === null || metricIndex === undefined ? '' : String(metricIndex);
    const key = `${devicePart}:${deviceIndexPart}:${metricPart}:${metricIndexPart}`;
    return computeHash(key) % CHART_COLOR_COUNT;
};

const getChartColorVar = (index: number): string => {
    const root = getDocumentElement();
    const computed = getComputedStyle(root);
    return computed.getPropertyValue(`--chart-color-${index}`).trim();
};

const getCssVarColor = (name: string): string => {
    const root = getDocumentElement();
    const computed = getComputedStyle(root);
    return computed.getPropertyValue(name).trim();
};

const getVendorBiasedColor = (subjectName: JsonValue | undefined): string | null => {
    const normalized = toTrimmedLower(subjectName);
    if (!normalized) return null;
    if (normalized.includes('amd') || normalized.includes('ati')) {
        const candidateValue = getCssVarColor('--chart-color-1') || getCssVarColor('--accent-red');
        return candidateValue ? candidateValue : null;
    }
    if (normalized.includes('nvidia')) {
        const candidateValue = getCssVarColor('--chart-color-0') || getCssVarColor('--accent-green');
        return candidateValue ? candidateValue : null;
    }
    if (normalized.includes('intel')) {
        const candidateValue = getCssVarColor('--chart-color-2') || getCssVarColor('--accent-blue');
        return candidateValue ? candidateValue : null;
    }
    return null;
};

const resolveChartColor = (mode: ChartColorMode, staticColor: JsonValue | undefined, device: JsonValue | undefined, deviceIndex: JsonValue | undefined, metric: JsonValue | undefined, metricIndex: JsonValue | undefined, subjectName?: JsonValue): string | null => {
    if (mode === 'disabled') return null;
    if (mode === 'static') return isString(staticColor) ? staticColor : null;
    const normalizedMetricIndex = Number(metricIndex);
    const vendorBiased = normalizedMetricIndex === 0 ? getVendorBiasedColor(subjectName) : null;
    if (vendorBiased) return vendorBiased;
    const index = getChartColorIndex(device, deviceIndex, metric, metricIndex);
    return getChartColorVar(index);
};

export { CHART_COLOR_COUNT, buildChartColorContext, getChartColorIndex, getChartColorVar, resolveChartColor };
export type { ChartColorMode };
