/* SoAI - Hardware feature chart transition [frontend/assets/ts/features/hardware/widgets/basehardwarewidget/chartTransition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleChartAnimationDurationMs, SERIES_TRANSITION_MS } from '@core/animations/chartMotion.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { waitForElementAnimations } from '@core/pageTransitions.ts';
import type { WidgetElements } from '@features/hardware/widgets/contracts.ts';

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
    const duration = scaleChartAnimationDurationMs(SERIES_TRANSITION_MS, chartSvg);
    if (duration === 0) {
        finishWidgetChartFadeIn(chartSvg, options);
        return;
    }
    const fadeIn = chartSvg.animate([{ opacity: 0 }, { opacity: 1 }], {
        duration,
        easing: 'ease',
        fill: 'forwards'
    });
    void waitForElementAnimations(chartSvg, { ensureStarted: false, animations: [fadeIn] }).then(
        () => finishWidgetChartFadeIn(chartSvg, options),
        (error) => {
            if (!isAbortError(error)) errorHandler.warn('HardwareWidgetChartTransition', 'Chart fade-in did not complete', ensureError(error));
            finishWidgetChartFadeIn(chartSvg, options);
        }
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
    const duration = scaleChartAnimationDurationMs(SERIES_TRANSITION_MS, chartSvg);
    if (duration === 0) {
        options.updateChartColor();
        finishWidgetChartFadeIn(chartSvg, options);
        return;
    }
    const fadeOut = chartSvg.animate([{ opacity: 1 }, { opacity: 0 }], {
        duration,
        easing: 'ease',
        fill: 'forwards'
    });
    void waitForElementAnimations(chartSvg, { ensureStarted: false, animations: [fadeOut] }).then(
        () => finishWidgetChartFadeOut(chartSvg, options),
        (error) => {
            if (!isAbortError(error)) errorHandler.warn('HardwareWidgetChartTransition', 'Chart fade-out did not complete', ensureError(error));
            finishWidgetChartFadeOut(chartSvg, options);
        }
    );
};

export { transitionHardwareWidgetChartMetric };
