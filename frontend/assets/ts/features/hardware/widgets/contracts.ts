/* SoAI - Hardware feature widgets boundary contracts [frontend/assets/ts/features/hardware/widgets/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import type { MetricConfig, WidgetSize } from '@features/hardware/widgets/constants.ts';

interface WidgetConfig<TData = JsonObject> {
    id?: string | undefined;
    name?: string | undefined;
    data?: TData | undefined;
    socketIndex?: number | undefined;
    sockets?: number | undefined;
    cores?: number | undefined;
    threads?: number | undefined;
    index?: number | undefined;
    deviceId?: string | undefined;
}

interface UnitConfig {
    current: string;
    alternatives: string[];
}

interface DeviceNameParts {
    primary: string;
    secondary: string | null;
}

interface DataPoint {
    timestamp: number;
    [key: string]: number;
}

interface HistoryData {
    timestampsMs?: number[] | undefined;
    data?: JsonObject[] | undefined;
}

interface WidgetElements {
    widgetLabel?: HTMLElement | undefined;
    deviceName?: HTMLElement | undefined;
    chartPath?: SVGPathElement | undefined;
    chartLine?: SVGPathElement | undefined;
    metricsContainer?: HTMLElement | undefined;
    metricRows?: Record<string, HTMLElement> | undefined;
    metricValues?: Record<string, HTMLElement> | undefined;
    metricIndicators?: Record<string, HTMLElement> | undefined;
}

type MetricChartNormalizer = (value: number, metric: string) => number;

interface WidgetOptions<TData = JsonObject> {
    container: HTMLElement;
    config: WidgetConfig<TData>;
    size?: WidgetSize | null | undefined;
}

type HardwareWidgetDataPoint = DataPoint;
type HardwareWidgetHistoryData = HistoryData;

export type { WidgetConfig, UnitConfig, DeviceNameParts, DataPoint, HistoryData, WidgetElements, MetricChartNormalizer, WidgetOptions, HardwareWidgetDataPoint, HardwareWidgetHistoryData, MetricConfig };
