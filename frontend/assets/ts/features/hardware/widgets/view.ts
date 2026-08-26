/* SoAI - Hardware feature widgets rendering [frontend/assets/ts/features/hardware/widgets/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { detectHardwareBrand, HARDWARE_BRANDS } from '@core/hardwareBrands.ts';
import { i18n } from '@core/i18n/index.ts';
import type { WidgetElements, DeviceNameParts } from '@features/hardware/widgets/contracts.ts';
import { WIDGET_CONSTANTS, type MetricConfig } from '@features/hardware/widgets/constants.ts';

interface WidgetStructureInput {
    container: HTMLElement;
    widgetId: string;
    labelText: string;
    nameParts: DeviceNameParts;
    metricsConfig: Record<string, MetricConfig>;
    availableMetrics: string[];
    defaultMetric: string;
}

const isLongDeviceName = (name: string): boolean => name.length > 30;

const applyWidgetSize = (container: HTMLElement, size: { WIDTH: number; HEIGHT: number }): void => {
    dom.setStyle(container, '--hardware-widget-width', `${size.WIDTH}px`);
    dom.setStyle(container, '--hardware-widget-height', `${size.HEIGHT}px`);
};

const applyWidgetManufacturerClass = (container: HTMLElement, name: string | undefined): void => {
    HARDWARE_BRANDS.forEach((brand: string) => dom.removeClass(container, `hardware-widget--${brand}`));
    const brand = detectHardwareBrand(name);
    dom.addClass(container, ['hardware-widget', `hardware-widget--${brand}`]);
};

const createElement = (tag: string, className?: string): HTMLElement => {
    const options = className ? { className } : {};
    return dom.create(tag, options);
};

const resolveMetricLabel = (metricKey: string): string => {
    switch (metricKey) {
        case 'core':
            return i18n.t('hardware.widgets.metrics.core');
        case 'ram':
            return i18n.t('hardware.widgets.metrics.ram');
        case 'vram':
            return i18n.t('hardware.widgets.metrics.vram');
        case 'power':
            return i18n.t('hardware.widgets.metrics.power');
        case 'temperature':
            return i18n.t('hardware.widgets.metrics.temperature');
        case 'download':
            return i18n.t('hardware.widgets.metrics.download');
        case 'upload':
            return i18n.t('hardware.widgets.metrics.upload');
        default:
            throw new Error(`Unsupported hardware widget metric label: ${metricKey}`);
    }
};

const createMetricRows = (
    container: HTMLElement,
    parameters: Pick<WidgetStructureInput, 'metricsConfig' | 'availableMetrics' | 'defaultMetric'>
): {
    metricRows: Record<string, HTMLElement>;
    metricValues: Record<string, HTMLElement>;
    metricIndicators: Record<string, HTMLElement>;
} => {
    const metricRows: Record<string, HTMLElement> = {};
    const metricValues: Record<string, HTMLElement> = {};
    const metricIndicators: Record<string, HTMLElement> = {};
    Object.keys(parameters.metricsConfig).forEach((key: string) => {
        if (!parameters.availableMetrics.includes(key)) {
            return;
        }

        const row = createElement('div', 'hardware-widget__metric-row');
        row.dataset['metric'] = key;

        const labelWrapper = createElement('div', 'hardware-widget__metric-label-wrapper');
        const labelChip = createElement('div', 'hardware-widget__metric-label-chip');

        const indicator = createElement('div', `hardware-widget__metric-indicator hardware-widget__metric-indicator--${key}`);
        if (key === parameters.defaultMetric) {
            dom.addClass(indicator, 'is-active');
        }
        metricIndicators[key] = indicator;

        const label = createElement('div', 'ui-metric-label');
        dom.setText(label, resolveMetricLabel(key));
        labelChip.append(indicator, label);
        labelWrapper.append(labelChip);

        if (key === parameters.defaultMetric) {
            const timeScale = createElement('div', 'hardware-widget__time-scale');
            dom.setText(timeScale, '5m');
            labelWrapper.append(timeScale);
        }

        const value = createElement('div', 'ui-metric-value');
        value.dataset['metric'] = key;
        metricValues[key] = value;

        row.append(labelWrapper, value);
        metricRows[key] = row;
        container.append(row);
    });

    return {
        metricRows,
        metricValues,
        metricIndicators
    };
};

const createWidgetStructure = (parameters: WidgetStructureInput): WidgetElements => {
    const widgetLabel = createElement('div', 'hardware-widget__label');
    dom.setText(widgetLabel, parameters.labelText);

    const fullName = parameters.nameParts.secondary ? `${parameters.nameParts.primary} ${parameters.nameParts.secondary}` : parameters.nameParts.primary;
    const deviceName = createElement('div', `hardware-widget__device-name${isLongDeviceName(fullName) ? ' hardware-widget__device-name--long' : ''}`);

    const chartContainer = createElement('div', 'hardware-widget__chart-container');
    const chartWrapper = createElement('div', 'hardware-widget__chart-wrapper');
    const chartSvg = dom.createSvgElement('svg', {
        className: 'hardware-widget__chart-svg',
        viewBox: `0 0 ${WIDGET_CONSTANTS.SVG_VIEWBOX} ${WIDGET_CONSTANTS.SVG_VIEWBOX}`,
        preserveAspectRatio: 'none'
    });

    const defs = dom.createSvgElement('defs');
    const gradient = dom.createSvgElement('linearGradient', {
        id: `gradient-${parameters.widgetId}`,
        x1: '0%',
        y1: '0%',
        x2: '0%',
        y2: '100%'
    });
    const stop1 = dom.createSvgElement('stop', { offset: '0%', className: 'hardware-widget__gradient-stop--start' });
    const stop2 = dom.createSvgElement('stop', { offset: '100%', className: 'hardware-widget__gradient-stop--end' });
    gradient.append(stop1, stop2);
    defs.append(gradient);

    const chartPath = dom.createSvgElement('path', {
        className: 'hardware-widget__chart-path',
        fill: `url(#gradient-${parameters.widgetId})`
    });
    const chartLine = dom.createSvgElement('path', {
        className: 'hardware-widget__chart-line',
        fill: 'none',
        'stroke-width': '1.5'
    });

    if (!(typeof SVGPathElement === 'function' && chartPath instanceof SVGPathElement)) {
        throw new Error('Hardware widget chartPath must be an SVGPathElement');
    }
    if (!(typeof SVGPathElement === 'function' && chartLine instanceof SVGPathElement)) {
        throw new Error('Hardware widget chartLine must be an SVGPathElement');
    }

    chartSvg.append(defs, chartPath, chartLine);
    chartWrapper.append(chartSvg);
    chartContainer.append(chartWrapper);

    const metricsContainer = createElement('div', 'hardware-widget__metrics');
    const { metricRows, metricValues, metricIndicators } = createMetricRows(metricsContainer, {
        metricsConfig: parameters.metricsConfig,
        availableMetrics: parameters.availableMetrics,
        defaultMetric: parameters.defaultMetric
    });

    const bottomBar = createElement('div', 'hardware-widget__bottom-bar');
    dom.setText(deviceName, parameters.nameParts.primary);

    const { secondary } = parameters.nameParts;
    if (secondary) {
        const secondaryNode = createElement('span', 'hardware-widget__device-name-secondary');
        dom.setText(secondaryNode, secondary);
        deviceName.append(secondaryNode);
    }

    parameters.container.append(widgetLabel, deviceName, chartContainer, metricsContainer, bottomBar);

    return {
        widgetLabel,
        deviceName,
        chartPath,
        chartLine,
        metricsContainer,
        metricRows,
        metricValues,
        metricIndicators
    };
};

export { applyWidgetSize, applyWidgetManufacturerClass, createWidgetStructure };
export type { WidgetStructureInput };
