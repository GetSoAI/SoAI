/* SoAI - Base hardware widget [frontend/assets/ts/features/hardware/widgets/BaseHardwareWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getWindow } from '@core/environment/public.ts';
import { LOCALIZATION_CHANGED_EVENT } from '@core/localization/public.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isPlainObject, isHTMLElement } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { WIDGET_SIZE, type WidgetSize } from '@features/hardware/widgets/constants.ts';
import { appendLiveDataPoint, buildWidgetChartPathValues, trimHistoricalDataPoints } from '@features/hardware/widgets/basehardwarewidget/effects.ts';
import { transitionHardwareWidgetChartMetric } from '@features/hardware/widgets/basehardwarewidget/chartTransition.ts';
import { applyHardwareWidgetChartColor, selectHardwareWidgetMetric, switchHardwareWidgetUnit, syncHardwareWidgetDefaultUnits, updateHardwareWidgetIdentityPresentation } from '@features/hardware/widgets/basehardwarewidget/service.ts';
import { bindHardwareWidgetInteractions } from '@features/hardware/widgets/events.ts';
import { applyWidgetManufacturerClass, applyWidgetSize, createWidgetStructure } from '@features/hardware/widgets/view.ts';
import type { DataPoint, DeviceNameParts, MetricConfig, HardwareWidgetHistoryData, UnitConfig, WidgetConfig, WidgetElements, WidgetOptions } from '@features/hardware/widgets/contracts.ts';

interface HardwareWidgetDefaults {
    metric: string;
    units: Record<string, UnitConfig>;
}

class BaseHardwareWidget<TData = JsonObject> {
    #container: HTMLElement;
    #config: WidgetConfig<TData>;
    #currentMetric: string;
    #dataPoints: DataPoint[] = [];
    #animationTimeouts: Map<HTMLElement, number> = new Map();
    #units: Record<string, UnitConfig>;
    #elements: WidgetElements = {};
    #size: WidgetSize;
    #resources: ResourceTracker = new ResourceTracker();
    #chartTransitionSequence = 0;
    #chartTransitioning = false;
    #unitOverrides: Set<string> = new Set();

    constructor({ container, config, size = null }: WidgetOptions<TData>, defaults: HardwareWidgetDefaults) {
        if (!isHTMLElement(container)) {
            throw new TypeError('BaseHardwareWidget requires a valid container element');
        }
        if (!isPlainObject(config)) {
            throw new TypeError('BaseHardwareWidget requires a valid config object');
        }
        this.#container = container;
        this.#config = { ...config };
        this.#size = isPlainObject(size) ? size : WIDGET_SIZE;
        this.#currentMetric = defaults.metric;
        this.#units = defaults.units;
    }

    get config(): WidgetConfig<TData> {
        return this.#config;
    }

    get dataPoints(): DataPoint[] {
        return this.#dataPoints;
    }

    get units(): Record<string, UnitConfig> {
        return this.#units;
    }

    get metricValueElements(): Record<string, HTMLElement> {
        return this.#elements.metricValues ?? {};
    }

    async initialize(): Promise<void> {
        applyWidgetSize(this.#container, this.#size);
        applyWidgetManufacturerClass(this.#container, this.#config.name);
        dom.addClass(this.#container, `hardware-widget--${this.getWidgetType()}`);
        this.#createStructure();
        this.#setupEventListeners();
        this.#updateChartColor();

        const initialData = this.#config.data;
        if (initialData) {
            this.updateData(initialData);
        } else {
            this.updateDisplayValues();
        }
    }

    #createStructure(): void {
        const nameData: DeviceNameParts = this.getDeviceNameParts();
        const widgetId = this.#config.id ?? 'hardware-widget';
        this.#elements = createWidgetStructure({
            container: this.#container,
            widgetId,
            labelText: this.getWidgetLabel(),
            nameParts: nameData,
            metricsConfig: this.getMetricsConfig(),
            availableMetrics: this.getAvailableMetrics(),
            defaultMetric: this.#currentMetric
        });
    }

    #setupEventListeners(): void {
        bindHardwareWidgetInteractions({
            container: this.#container,
            resources: this.#resources,
            handlers: {
                onMetricSelect: (metric: string) => {
                    this.selectMetric(metric);
                },
                onMetricUnitSwitch: (metric: string, element: HTMLElement) => {
                    const units = this.#units[metric];
                    if (!units) {
                        return;
                    }
                    this.#switchUnit(metric, element);
                }
            }
        });
        this.#resources.addEventListener(getWindow(), LOCALIZATION_CHANGED_EVENT, () => this.#syncDefaultUnits());
    }

    selectMetric(metric: string): void {
        selectHardwareWidgetMetric(
            this.#container,
            this.#elements,
            this.#currentMetric,
            metric,
            () => this.getAvailableMetrics(),
            (value: string) => {
                this.#currentMetric = value;
            },
            () => {
                this.#transitionChartMetric();
            }
        );
    }

    #updateChartColor(): void {
        applyHardwareWidgetChartColor(this.#container, this.#elements, this.#currentMetric, this.getMetricsConfig());
    }

    #switchUnit(metric: string, element: HTMLElement): void {
        const switched = switchHardwareWidgetUnit(metric, element, this.#units, this.#resources, this.#animationTimeouts, () => this.updateDisplayValues());
        if (switched) {
            this.#unitOverrides.add(metric);
        }
    }

    #syncDefaultUnits(): void {
        const changed = syncHardwareWidgetDefaultUnits(this.#units, this.getUnitConfig(), this.#unitOverrides);
        if (changed) {
            this.updateDisplayValues();
        }
    }

    updateConfig(newConfig: Partial<WidgetConfig<TData>>): void {
        if (!isPlainObject(newConfig)) {
            return;
        }

        const nameChanged = newConfig.name && newConfig.name !== this.#config.name;
        Object.assign(this.#config, newConfig);

        if (nameChanged) {
            applyWidgetManufacturerClass(this.#container, this.#config.name);
            updateHardwareWidgetIdentityPresentation(
                this.#elements,
                () => this.getDeviceNameParts(),
                () => this.getWidgetLabel()
            );
        }
    }

    updateData(data: TData): void {
        this.#config.data = { ...data };
        const nextPoint = this.createDataPoint(data);
        this.#dataPoints = appendLiveDataPoint(this.#dataPoints, nextPoint, serverEpochMs());

        this.updateDisplayValues();
        this.updateChart();
    }

    processHistoricalData(historyData: HardwareWidgetHistoryData): void {
        if (!isPlainObject(historyData)) {
            return;
        }
        const points = this.transformHistoricalData(historyData);
        if (points.length > 0) {
            this.#dataPoints = trimHistoricalDataPoints(points);
            this.updateChart();
        }
    }

    updateChart(): void {
        if (this.#chartTransitioning) {
            return;
        }
        this.#renderCurrentChart();
    }

    #renderCurrentChart(): void {
        const chartPath = this.#elements.chartPath;
        const chartLine = this.#elements.chartLine;
        if (!chartPath || !chartLine) {
            return;
        }

        const paths = buildWidgetChartPathValues(this.#dataPoints, this.#currentMetric, serverEpochMs(), (value, metric) => this.normalizeChartMetricValue(value, metric));
        chartPath.setAttribute('d', paths.areaPath);
        chartLine.setAttribute('d', paths.linePath);
    }

    #transitionChartMetric(): void {
        const sequence = this.#chartTransitionSequence + 1;
        this.#chartTransitionSequence = sequence;
        this.#chartTransitioning = true;
        transitionHardwareWidgetChartMetric({
            elements: this.#elements,
            sequence,
            isCurrent: (value: number): boolean => value === this.#chartTransitionSequence,
            setTransitioning: (value: boolean): void => {
                if (sequence === this.#chartTransitionSequence) {
                    this.#chartTransitioning = value;
                }
            },
            updateChartColor: (): void => this.#updateChartColor(),
            renderCurrentChart: (): void => this.#renderCurrentChart()
        });
    }

    destroy(): void {
        this.#chartTransitionSequence += 1;
        this.#chartTransitioning = false;
        this.#resources.cleanup();
        this.#animationTimeouts.clear();
        this.#dataPoints = [];
        dom.setText(this.#container, '');
        this.#elements = {};
    }

    getWidgetType(): string {
        throw new Error('getWidgetType must be implemented by subclass');
    }

    getDefaultMetric(): string {
        throw new Error('getDefaultMetric must be implemented by subclass');
    }

    getMetricsConfig(): Record<string, MetricConfig> {
        throw new Error('getMetricsConfig must be implemented by subclass');
    }

    getUnitConfig(): Record<string, UnitConfig> {
        throw new Error('getUnitConfig must be implemented by subclass');
    }

    getDeviceNameParts(): DeviceNameParts {
        throw new Error('getDeviceNameParts must be implemented by subclass');
    }

    getWidgetLabel(): string {
        throw new Error('getWidgetLabel must be implemented by subclass');
    }

    createDataPoint(_data: TData): DataPoint {
        throw new Error('createDataPoint must be implemented by subclass');
    }

    transformHistoricalData(_historyData: HardwareWidgetHistoryData): DataPoint[] {
        throw new Error('transformHistoricalData must be implemented by subclass');
    }

    updateDisplayValues(): void {
        throw new Error('updateDisplayValues must be implemented by subclass');
    }

    getAvailableMetrics(): string[] {
        throw new Error('getAvailableMetrics must be implemented by subclass');
    }

    normalizeChartMetricValue(value: number, _metric: string): number {
        return value;
    }
}

export { BaseHardwareWidget };
