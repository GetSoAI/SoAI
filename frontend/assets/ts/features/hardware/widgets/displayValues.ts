/* SoAI - Hardware feature display values [frontend/assets/ts/features/hardware/widgets/displayValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { resolveTemperatureSeverity } from '@features/hardware/thermalSeverity.ts';

const updateTemperatureDisplay = (element: Element, rawTemp: number | null, unit: string): void => {
    if (rawTemp === null) {
        dom.setText(element, '');
        dom.toggleClass(element, 'hardware-widget__metric-value--temperature-critical', false);
        dom.toggleClass(element, 'hardware-widget__metric-value--temperature-warning', false);
        return;
    }
    const displayTemp = unit === 'F' ? Math.round((rawTemp * 9) / 5 + 32) : rawTemp;
    const severity = resolveTemperatureSeverity(rawTemp);
    dom.setText(element, `${displayTemp}°${unit}`);
    dom.toggleClass(element, 'hardware-widget__metric-value--temperature-critical', severity === 'critical');
    dom.toggleClass(element, 'hardware-widget__metric-value--temperature-warning', severity === 'warning');
};

export { updateTemperatureDisplay };
