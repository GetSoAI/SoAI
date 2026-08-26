/* SoAI - Metrics page DOM contracts [frontend/assets/ts/pages/metrics/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { METRICS_ACTION_EXPORT, METRICS_ACTION_MORE } from '@pages/metrics/actions.ts';
import type { MetricsRuntimeContext } from '@pages/metrics/controllers/page/contracts.ts';

type MetricsPageDomHost = Pick<MetricsRuntimeContext, 'owners' | 'operations'>;

type MetricsUi = {
    root: HTMLElement;
};

const optionalMetricsRoot = (page: MetricsPageDomHost): HTMLElement | null => {
    const root = page.operations.getDomContext();
    return root instanceof HTMLElement ? root : null;
};

const requireMetricsRoot = (page: MetricsPageDomHost): HTMLElement => {
    const root = page.operations.getDomContext();
    if (!(root instanceof HTMLElement)) {
        throw new Error('Metrics page requires a host container');
    }
    return root;
};

const requireExportButton = (page: MetricsPageDomHost): HTMLElement => {
    const root = requireMetricsRoot(page);
    const button = page.owners.pageDom.requireHTMLElement('#metrics-export-btn', root);
    if (requireTrimmedDataAttribute(button, 'action', 'Metrics export button') !== METRICS_ACTION_EXPORT) {
        throw new Error('Metrics export button requires correct data-action attribute');
    }
    return button;
};

const requireMoreButton = (page: MetricsPageDomHost): HTMLElement => {
    const root = requireMetricsRoot(page);
    const button = page.owners.pageDom.requireHTMLElement('#metrics-more-btn', root);
    if (requireTrimmedDataAttribute(button, 'action', 'Metrics more button') !== METRICS_ACTION_MORE) {
        throw new Error('Metrics more button requires correct data-action attribute');
    }
    return button;
};

const requireMetricsUi = (page: MetricsPageDomHost): MetricsUi => {
    const root = requireMetricsRoot(page);
    requireExportButton(page);
    requireMoreButton(page);
    return { root };
};

export { optionalMetricsRoot, requireMetricsUi };
export type { MetricsUi, MetricsPageDomHost };
