/* SoAI - Hardware feature chart transition [frontend/assets/ts/features/hardware/widgets/basehardwarewidget/chartTransition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { dom } from '@core/dom/dom.ts';
import type { WidgetElements } from '@features/hardware/widgets/contracts.ts';

const WIDGET_CHART_TRANSITION_DURATION_MS = 240;

interface HardwareWidgetChartTransitionOptions {
    elements: WidgetElements;
    sequence: number;
    isCurrent(sequence: number): boolean;
    setTransitioning(value: boolean): void;
    updateChartColor(): void;
    renderCurrentChart(): void;
}

const finishWidgetChartFadeIn = (chartSvg: SVGSVGElement, options: HardwareWidgetChartTransitionOptions): void => {
    if (!options.isCurrent(options.sequence)) {
        return;
    }
    options.setTransitioning(false);
    chartSvg.getAnimations().forEach((animation) => animation.cancel());
    dom.setStyle(chartSvg, 'opacity', '');
    options.renderCurrentChart();
};

const finishWidgetChartFadeOut = (chartSvg: SVGSVGElement, options: HardwareWidgetChartTransitionOptions): void => {
    if (!options.isCurrent(options.sequence)) {
        return;
    }
    options.updateChartColor();
    options.renderCurrentChart();
    const duration = scaleAnimationDurationMs(WIDGET_CHART_TRANSITION_DURATION_MS, chartSvg);
    const fadeIn = chartSvg.animate([{ opacity: 0 }, { opacity: 1 }], {
        duration,
        easing: 'ease',
        fill: 'forwards'
    });
    void fadeIn.finished.then(
        () => finishWidgetChartFadeIn(chartSvg, options),
        () => finishWidgetChartFadeIn(chartSvg, options)
    );
};

const transitionHardwareWidgetChartMetric = (options: HardwareWidgetChartTransitionOptions): void => {
    const chartPath = options.elements.chartPath;
    const chartLine = options.elements.chartLine;
    if (!chartPath || !chartLine) {
        options.updateChartColor();
        options.renderCurrentChart();
        options.setTransitioning(false);
        return;
    }
    const chartSvg = chartPath.ownerSVGElement;
    if (!chartSvg) {
        throw new Error('Hardware widget chart path must be attached to an SVG element');
    }
    chartSvg.getAnimations().forEach((animation) => animation.cancel());
    const duration = scaleAnimationDurationMs(WIDGET_CHART_TRANSITION_DURATION_MS, chartSvg);
    const fadeOut = chartSvg.animate([{ opacity: 1 }, { opacity: 0 }], {
        duration,
        easing: 'ease',
        fill: 'forwards'
    });
    void fadeOut.finished.then(
        () => finishWidgetChartFadeOut(chartSvg, options),
        () => finishWidgetChartFadeOut(chartSvg, options)
    );
};

export { transitionHardwareWidgetChartMetric };
