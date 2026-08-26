/* SoAI - Metrics page rendering [frontend/assets/ts/pages/metrics/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';

import { uiHtml } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { KPI_CONFIG } from '@features/metrics/public.ts';
import { METRICS_ACTION_EXPORT, METRICS_ACTION_MORE } from '@pages/metrics/actions.ts';
import { METRICS_GRID_SETTINGS } from '@pages/metrics/rendering/layout/constants.ts';

type GetIconSyncFunctionValue = (iconName: IconName, options?: IconOptions) => TrustedHtml;
type GenerateStandardHeaderFunctionValue = (options: GenerateStandardHeaderOptions) => TrustedHtml;

type MetricsPageViewDependencies = {
    getIconSync: GetIconSyncFunctionValue;
    generateStandardHeader: GenerateStandardHeaderFunctionValue;
};

const renderMetricsPageView = ({ getIconSync, generateStandardHeader }: MetricsPageViewDependencies): TrustedHtml => {
    const exportLabel = i18n.t('common.export');
    const moreLabel = i18n.t('metrics.advanced.moreButton');
    const exportIcon = getIconSync('download', { size: 24, strokeWidth: 1.5 });
    const moreIcon = getIconSync('ellipsis', { size: 24, strokeWidth: 1.5 });
    const header = generateStandardHeader({
        title: i18n.t('metrics.header.title'),
        description: i18n.t('metrics.header.description'),
        actions: [
            {
                type: 'button',
                content: uiHtml`${exportIcon}<span>${exportLabel}</span>`,
                id: 'metrics-export-btn',
                ariaLabel: exportLabel,
                attributes: { 'data-action': METRICS_ACTION_EXPORT }
            },
            {
                type: 'button',
                content: uiHtml`${moreIcon}<span>${moreLabel}</span>`,
                id: 'metrics-more-btn',
                ariaLabel: moreLabel,
                attributes: { 'data-action': METRICS_ACTION_MORE }
            }
        ],
        stats: KPI_CONFIG.map((entry) => ({ id: entry.id, label: entry.getLabel() })),
        contentLayout: 'analytics'
    });
    const content = uiHtml`<div class="metrics-content analytics-stack"><div id="metrics-grid" class="metrics-movable-grid movable-sections-grid" data-columns="${METRICS_GRID_SETTINGS.columns}"></div></div>`;
    return toTrustedUiHtml(header.html.replace('<!-- Page content goes here -->', content.html));
};

export { renderMetricsPageView };
export type { MetricsPageViewDependencies };
