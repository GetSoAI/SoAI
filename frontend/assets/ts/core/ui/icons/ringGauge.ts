/* SoAI - Shared rounded ring gauge graphics [frontend/assets/ts/core/ui/icons/ringGauge.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

interface RingGaugeOptions {
    className: string;
    strokeWidth: number;
    startAngle: number;
    track?: boolean;
}

const createRingGauge = (options: RingGaugeOptions): SVGElement => {
    const gauge = dom.createSvgElement('svg', { class: `ui-ring-gauge ${options.className}`, viewBox: '0 0 100 100', 'aria-hidden': 'true', focusable: 'false' });
    const createCircle = (className: string): SVGElement =>
        dom.createSvgElement('circle', {
            class: className,
            cx: '50',
            cy: '50',
            r: String((100 - options.strokeWidth) / 2),
            'stroke-width': String(options.strokeWidth),
            pathLength: '100',
            transform: `rotate(${options.startAngle} 50 50)`
        });
    if (options.track) gauge.append(createCircle('ui-ring-gauge-track'));
    gauge.append(createCircle('ui-ring-gauge-fill'));
    updateRingGauge(gauge, 0);
    return gauge;
};

const updateRingGauge = (gauge: SVGElement, percent: number): void => {
    const value = Number.isFinite(percent) ? Math.min(100, Math.max(0, percent)) : 0;
    const fill = dom.resolve('.ui-ring-gauge-fill', gauge);
    if (!(fill instanceof SVGElement)) throw new Error('Ring gauge requires its fill circle');
    fill.style.setProperty('stroke-dasharray', `${value} 100`);
    gauge.setAttribute('data-ring-gauge-empty', String(value === 0));
};

export { createRingGauge, updateRingGauge };
