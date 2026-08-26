/* SoAI - Metrics page events [frontend/assets/ts/pages/metrics/controllers/page/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';
import { applyAdaptiveNumbers } from '@core/ui/adaptiveNumber.ts';
import { openMetricsAdvancedModal } from '@features/metrics/public.ts';
import { METRICS_ACTION_EXPORT, METRICS_ACTION_MORE, METRICS_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE, METRICS_ACTION_SORT, type MetricsActionId } from '@pages/metrics/actions.ts';
import { openMetricsExportPreview } from '@pages/metrics/controllers/page/adapters.ts';
import type { MetricsPageEventHost } from '@pages/metrics/controllers/page/contracts.ts';
import { handleMetricsRootSortAction, initializeMetricsTables } from '@pages/metrics/controllers/page/tables.ts';
import { requireMetricsUi } from '@pages/metrics/dom.ts';
import { toggleMetricsRequestDistributionSource } from '@pages/metrics/widgets/effects.ts';

const handleMetricsRootClick = (host: MetricsPageEventHost, action: MetricsActionId, actionElement: Element, event: Event): void | Promise<void> => {
    if (event.defaultPrevented) {
        return;
    }
    if (action === METRICS_ACTION_EXPORT) {
        event.preventDefault();
        event.stopPropagation();
        return openMetricsExportPreview(host);
    }
    if (action === METRICS_ACTION_MORE) {
        event.preventDefault();
        event.stopPropagation();
        openMetricsAdvancedModal();
        return;
    }
    if (action === METRICS_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE) {
        event.preventDefault();
        event.stopPropagation();
        toggleMetricsRequestDistributionSource(host);
        return;
    }
    if (action === METRICS_ACTION_SORT) {
        event.preventDefault();
        event.stopPropagation();
        handleMetricsRootSortAction(host, actionElement);
    }
};

const handleMetricsRootKeydown = (host: MetricsPageEventHost, action: MetricsActionId, actionElement: Element, event: KeyboardEvent): void => {
    if (event.defaultPrevented) {
        return;
    }
    if (event.key !== 'Enter' && event.key !== ' ') {
        return;
    }
    if (action !== METRICS_ACTION_SORT) {
        return;
    }
    event.preventDefault();
    event.stopPropagation();
    handleMetricsRootSortAction(host, actionElement);
};

const setupMetricsPageUiEffects = (host: MetricsPageEventHost, signal: AbortSignal): void => {
    const ui = requireMetricsUi(host);

    const win = getWindow();
    let adaptiveNumbersTimer: number | null = null;
    const scheduleAdaptiveNumbers = (): void => {
        if (adaptiveNumbersTimer !== null) {
            win.clearTimeout(adaptiveNumbersTimer);
        }
        adaptiveNumbersTimer = win.setTimeout(() => {
            adaptiveNumbersTimer = null;
            applyAdaptiveNumbers(ui.root);
        }, 150);
    };

    win.addEventListener('resize', scheduleAdaptiveNumbers, { signal });
    signal.addEventListener(
        'abort',
        () => {
            if (adaptiveNumbersTimer !== null) {
                win.clearTimeout(adaptiveNumbersTimer);
                adaptiveNumbersTimer = null;
            }
            host.state.distributionChartSizeWatcher.disconnect();
        },
        { once: true }
    );

    initializeMetricsTables(host);
    applyAdaptiveNumbers(ui.root);
};

export { handleMetricsRootClick, handleMetricsRootKeydown, setupMetricsPageUiEffects };
