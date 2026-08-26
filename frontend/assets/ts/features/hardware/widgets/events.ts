/* SoAI - Hardware feature widgets events [frontend/assets/ts/features/hardware/widgets/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isElementNode } from '@core/typeGuards.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

interface WidgetInteractionHandlers {
    onMetricSelect: (metric: string) => void;
    onMetricUnitSwitch: (metric: string, element: HTMLElement) => void;
}

interface WidgetInteractionParameters {
    container: HTMLElement;
    resources: ResourceTracker;
    handlers: WidgetInteractionHandlers;
}

const bindHardwareWidgetInteractions = (parameters: WidgetInteractionParameters): void => {
    parameters.resources.addEventListener(parameters.container, 'click', (error: Event) => {
        if (!isElementNode(error.target)) {
            return;
        }

        const labelElement = error.target.closest('.ui-metric-label');
        if (labelElement && labelElement instanceof HTMLElement) {
            error.stopPropagation();
            const row = labelElement.closest('.hardware-widget__metric-row');
            if (row instanceof HTMLElement) {
                const metric = row.dataset['metric'];
                if (metric) {
                    parameters.handlers.onMetricSelect(metric);
                }
            }
            return;
        }

        const valueElement = error.target.closest('.ui-metric-value');
        if (valueElement instanceof HTMLElement) {
            error.stopPropagation();
            const metric = valueElement.dataset['metric'];
            if (metric) {
                parameters.handlers.onMetricUnitSwitch(metric, valueElement);
            }
        }
    });
};

export { bindHardwareWidgetInteractions };
export type { WidgetInteractionParameters, WidgetInteractionHandlers };
