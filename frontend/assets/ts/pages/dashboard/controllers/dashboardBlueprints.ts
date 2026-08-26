/* SoAI - Dashboard page blueprints [frontend/assets/ts/pages/dashboard/controllers/dashboardBlueprints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import type { RequestDistributionSource } from '@core/models/requestDistribution.ts';
import { resolveRequestDistributionSourceToggleLabel } from '@core/models/requestDistributionRendering.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE, DASHBOARD_ACTION_LOGS_SIZE_DECREASE, DASHBOARD_ACTION_LOGS_SIZE_INCREASE, DASHBOARD_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE, DASHBOARD_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID } from '@pages/dashboard/actions.ts';
import { formatLogsAutoScrollLabel } from '@pages/dashboard/widgets/logs/LogsLabelsWidget.ts';

type DashboardBlueprintId = 'status' | 'logs' | 'plugins' | 'models' | 'hardwareWidgets' | 'network' | 'storage' | 'imagecard' | 'memo' | 'requests' | 'productCapabilities' | 'clock' | 'throughput' | 'quickActions';

const isDashboardBlueprintId = (value: string): value is DashboardBlueprintId => {
    switch (value) {
        case 'status':
        case 'logs':
        case 'plugins':
        case 'models':
        case 'hardwareWidgets':
        case 'network':
        case 'storage':
        case 'imagecard':
        case 'memo':
        case 'requests':
        case 'productCapabilities':
        case 'clock':
        case 'throughput':
        case 'quickActions':
            return true;
        default:
            return false;
    }
};

interface DashboardBlueprintRendererSet {
    renderStatusSection: () => void;
    renderProductCapabilitiesSection: () => void;
    renderPluginsSection: () => void;
    renderModelsSection: () => void;
    renderHardwareWidgetsSection: () => Promise<void>;
    renderNetworkInterfacesSection: () => void;
    renderStorageSection: () => void;
    renderImageCardSection: () => void;
    renderMemoSection: () => void;
    renderClockSection: () => void;
    renderThroughputSection: () => void;
    renderQuickActionsSection: () => void;
    renderRequestsSection: () => void;
    renderLogs: () => void;
    getRequestDistributionSource: () => RequestDistributionSource;
    getRequestDistributionNextSource: () => RequestDistributionSource;
    buildImageCardControls: () => TrustedHtml;
    buildMemoControls: () => TrustedHtml;
}

interface DashboardBlueprintsDependencies {
    renderers: DashboardBlueprintRendererSet;
    includeProductCapabilities: boolean;
}

interface DashboardBlueprint {
    layout: { x: number; y: number; width: number; height: number };
    render: () => void | Promise<void>;
    showSubtitle: boolean;
    controls?: () => TrustedHtml;
}

interface CollectionSectionConfig {
    contentId: string;
    dataType: 'plugins' | 'models';
    items: JsonValue[];
    emptyKey: string;
    itemType: string;
    totalLabelKey: string;
    countedLabelKey: string;
    isCounted: (item: JsonValue) => boolean;
    statusGetter: (item: JsonValue) => string;
    nameKeys: string[];
    idKeys: string[];
    unknownNameKey: string;
}

const createDashboardBlueprints = (dependencies: DashboardBlueprintsDependencies): Map<DashboardBlueprintId, DashboardBlueprint> => {
    const textBtn = (label: string, attr: string, variant: string = 'ui-variant-neutral'): string => `<button type="button" class="ui-button ui-button--titlebar ${variant}" aria-label="${label}" data-tooltip="${label}" ${attr}>${label}</button>`;
    const blueprints: Map<DashboardBlueprintId, DashboardBlueprint> = new Map([
        [
            'status',
            {
                layout: { x: 0, y: 0, width: 1, height: 1 },
                render: () => dependencies.renderers.renderStatusSection(),
                showSubtitle: false
            }
        ],
        [
            'logs',
            {
                layout: { x: 1, y: 0, width: 4, height: 1 },
                render: () => dependencies.renderers.renderLogs(),
                showSubtitle: false,
                controls: () => {
                    const sizeDecreaseLabel = i18n.t('dashboard.sections.logs.sizeDecrease');
                    const sizeIncreaseLabel = i18n.t('dashboard.sections.logs.sizeIncrease');
                    const autoScrollLabel = formatLogsAutoScrollLabel(true);
                    const sizeDecrease = `<button type="button" id="logs-size-decrease" data-action="${DASHBOARD_ACTION_LOGS_SIZE_DECREASE}" class="ui-button ui-button--titlebar ui-variant-neutral" aria-label="${sizeDecreaseLabel}" data-tooltip="${sizeDecreaseLabel}">${renderIconSlot(getIconSync('minus', { size: 14, strokeWidth: 1.6 }))}</button>`;
                    const sizeIncrease = `<button type="button" id="logs-size-increase" data-action="${DASHBOARD_ACTION_LOGS_SIZE_INCREASE}" class="ui-button ui-button--titlebar ui-variant-neutral" aria-label="${sizeIncreaseLabel}" data-tooltip="${sizeIncreaseLabel}">${renderIconSlot(getIconSync('add', { size: 14, strokeWidth: 1.6 }))}</button>`;
                    const autoScroll = textBtn(autoScrollLabel, `id="logs-autoscroll" data-action="${DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE}" aria-pressed="true"`);
                    return toTrustedUiHtml(`<div class="logs-controls"><div class="logs-size-controls">${sizeIncrease}${sizeDecrease}</div>${autoScroll}</div>`);
                }
            }
        ],
        [
            'plugins',
            {
                layout: { x: 0, y: 1, width: 1, height: 1 },
                render: () => dependencies.renderers.renderPluginsSection(),
                showSubtitle: false
            }
        ],
        [
            'models',
            {
                layout: { x: 1, y: 1, width: 1, height: 1 },
                render: () => dependencies.renderers.renderModelsSection(),
                showSubtitle: false
            }
        ],
        [
            'hardwareWidgets',
            {
                layout: { x: 2, y: 1, width: 3, height: 1 },
                render: () => dependencies.renderers.renderHardwareWidgetsSection(),
                showSubtitle: false
            }
        ],
        [
            'network',
            {
                layout: { x: 1, y: 2, width: 2, height: 1 },
                render: () => dependencies.renderers.renderNetworkInterfacesSection(),
                showSubtitle: false,
                controls: () => uiHtml`<span class="u-text-muted" id="dashboardNetworkSummary">${i18n.t('hardware.common.detecting')}</span>`
            }
        ],
        [
            'storage',
            {
                layout: { x: 3, y: 2, width: 2, height: 1 },
                render: () => dependencies.renderers.renderStorageSection(),
                showSubtitle: false,
                controls: () => uiHtml`<span class="u-text-muted" id="dashboardStorageSummary">${i18n.t('hardware.common.detecting')}</span>`
            }
        ],
        [
            'imagecard',
            {
                layout: { x: 0, y: 3, width: 1, height: 1 },
                render: () => dependencies.renderers.renderImageCardSection(),
                showSubtitle: false,
                controls: () => dependencies.renderers.buildImageCardControls()
            }
        ],
        [
            'memo',
            {
                layout: { x: 1, y: 3, width: 1, height: 1 },
                render: () => dependencies.renderers.renderMemoSection(),
                showSubtitle: false,
                controls: () => dependencies.renderers.buildMemoControls()
            }
        ],
        [
            'requests',
            {
                layout: { x: 0, y: 2, width: 1, height: 1 },
                render: () => dependencies.renderers.renderRequestsSection(),
                showSubtitle: false,
                controls: () => {
                    const source = dependencies.renderers.getRequestDistributionSource();
                    const label = resolveRequestDistributionSourceToggleLabel(dependencies.renderers.getRequestDistributionNextSource());
                    const icon = renderIconSlot(getIconSync('request-distribution-source', { size: 14, strokeWidth: 1.8 }));
                    return toTrustedUiHtml(`<button type="button" id="${DASHBOARD_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID}" class="ui-icon-button ui-icon-button--titlebar ui-variant-neutral" data-action="${DASHBOARD_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE}" aria-label="${label}" data-tooltip="${label}" aria-pressed="${source === 'model' ? 'false' : 'true'}">${icon}</button>`);
                }
            }
        ],
        [
            'clock',
            {
                layout: { x: 0, y: 4, width: 1, height: 1 },
                render: () => dependencies.renderers.renderClockSection(),
                showSubtitle: false
            }
        ],
        [
            'throughput',
            {
                layout: { x: 0, y: 4, width: 1, height: 1 },
                render: () => dependencies.renderers.renderThroughputSection(),
                showSubtitle: false
            }
        ],
        [
            'quickActions',
            {
                layout: { x: 1, y: 4, width: 1, height: 1 },
                render: () => dependencies.renderers.renderQuickActionsSection(),
                showSubtitle: false
            }
        ]
    ]);

    if (dependencies.includeProductCapabilities) {
        blueprints.set('productCapabilities', {
            layout: { x: 2, y: 3, width: 2, height: 1 },
            render: () => dependencies.renderers.renderProductCapabilitiesSection(),
            showSubtitle: false
        });
    }

    return blueprints;
};

export { createDashboardBlueprints };
export { isDashboardBlueprintId };
export type { CollectionSectionConfig, DashboardBlueprint, DashboardBlueprintId };
