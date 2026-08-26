/* SoAI - Base hardware widget service [frontend/assets/ts/features/hardware/widgets/basehardwarewidget/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { resolveDeviceNamePresentation } from '@features/hardware/widgets/basehardwarewidget/mappers.ts';
import type { DeviceNameParts, MetricConfig, UnitConfig, WidgetElements } from '@features/hardware/widgets/contracts.ts';

const applyHardwareWidgetChartColor = (container: HTMLElement, elements: WidgetElements, currentMetric: string, metricsConfig: Record<string, MetricConfig>): void => {
    const config = metricsConfig[currentMetric];
    if (!config) {
        return;
    }

    const colorVar = config.colorVar;
    dom.setStyle(container, '--hardware-widget-chart-color', `var(${colorVar})`);

    if (elements.chartPath) {
        elements.chartPath.classList.value = `hardware-widget__chart-path hardware-widget__chart--${currentMetric}`;
    }
    if (elements.chartLine) {
        elements.chartLine.classList.value = `hardware-widget__chart-line hardware-widget__chart--${currentMetric}`;
    }
};

const selectHardwareWidgetMetric = (container: HTMLElement, elements: WidgetElements, currentMetric: string, metric: string, getAvailableMetrics: () => string[], setCurrentMetric: (value: string) => void, onMetricChanged: () => void): void => {
    if (currentMetric === metric || !metric) {
        return;
    }

    const availableMetrics = getAvailableMetrics();
    if (!availableMetrics.includes(metric)) {
        return;
    }

    setCurrentMetric(metric);

    Object.values(elements.metricIndicators ?? {}).forEach((element) => dom.removeClass(element, 'is-active'));
    dom.resolveAll('.hardware-widget__time-scale', container).forEach((element) => element.remove());

    const indicator = elements.metricIndicators?.[metric];
    if (indicator) {
        dom.addClass(indicator, 'is-active');
    }

    const row = elements.metricRows?.[metric];
    if (row) {
        const labelWrapper = dom.resolve('.hardware-widget__metric-label-wrapper', row);
        if (labelWrapper) {
            const timeScale = dom.create('div', { className: 'hardware-widget__time-scale' });
            dom.setText(timeScale, '5m');
            labelWrapper.append(timeScale);
        }
    }

    onMetricChanged();
};

type TimerHost = {
    setTimeout: (callback: (() => void) | undefined, delay: number) => number;
    clearTimer: (timerId: number) => void;
};

const switchHardwareWidgetUnit = (metric: string, element: HTMLElement, units: Record<string, UnitConfig>, timers: TimerHost, animationTimeouts: Map<HTMLElement, number>, onUnitSwitched: () => void): boolean => {
    if (animationTimeouts.has(element)) {
        const existingTimeout = animationTimeouts.get(element);
        if (existingTimeout !== undefined) {
            timers.clearTimer(existingTimeout);
        }
        dom.removeClass(element, 'is-unit-switching');
    }

    const unitConfig = units[metric];
    if (!unitConfig) {
        return false;
    }

    const alternatives = unitConfig.alternatives;
    if (!alternatives.length) {
        throw new Error(`Hardware widget unit alternatives for "${metric}" must not be empty`);
    }
    const currentIndex = alternatives.indexOf(unitConfig.current);
    const nextIndex = (currentIndex + 1 + alternatives.length) % alternatives.length;
    const nextUnit = alternatives[nextIndex];
    if (!nextUnit) {
        throw new Error(`Hardware widget unit alternative ${nextIndex} for "${metric}" is missing`);
    }
    unitConfig.current = nextUnit;
    onUnitSwitched();

    dom.addClass(element, 'is-unit-switching');
    animationTimeouts.set(
        element,
        timers.setTimeout(() => {
            dom.removeClass(element, 'is-unit-switching');
            animationTimeouts.delete(element);
        }, 300)
    );
    return true;
};

const syncHardwareWidgetDefaultUnits = (units: Record<string, UnitConfig>, nextDefaults: Record<string, UnitConfig>, overriddenMetrics: ReadonlySet<string>): boolean => {
    let changed = false;
    for (const [metric, nextDefault] of Object.entries(nextDefaults)) {
        if (overriddenMetrics.has(metric)) {
            continue;
        }
        const current = units[metric];
        if (!current) {
            units[metric] = { current: nextDefault.current, alternatives: [...nextDefault.alternatives] };
            changed = true;
            continue;
        }
        current.alternatives = [...nextDefault.alternatives];
        if (current.current !== nextDefault.current) {
            current.current = nextDefault.current;
            changed = true;
        }
    }
    return changed;
};

const updateHardwareWidgetIdentityPresentation = (elements: WidgetElements, getDeviceNameParts: () => DeviceNameParts, getWidgetLabel: () => string): void => {
    const deviceName = elements.deviceName;
    if (deviceName) {
        const nameData = getDeviceNameParts();
        const presentation = resolveDeviceNamePresentation({ parts: nameData });
        deviceName.className = presentation.className;
        dom.setText(deviceName, presentation.primary);
        if (presentation.secondary) {
            const secondary = dom.create('span', { className: 'hardware-widget__device-name-secondary' });
            dom.setText(secondary, presentation.secondary);
            deviceName.append(secondary);
        }
    }

    const widgetLabel = elements.widgetLabel;
    if (widgetLabel) {
        dom.setText(widgetLabel, getWidgetLabel());
    }
};

export { applyHardwareWidgetChartColor, selectHardwareWidgetMetric, switchHardwareWidgetUnit, syncHardwareWidgetDefaultUnits, updateHardwareWidgetIdentityPresentation };
