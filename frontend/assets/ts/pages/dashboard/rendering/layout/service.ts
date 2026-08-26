/* SoAI - Dashboard movable section layout service [frontend/assets/ts/pages/dashboard/rendering/layout/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { MovableSectionLayoutConfig } from '@core/routing/pages/movablesections/types.ts';
import { isDashboardBlueprintId, type DashboardBlueprintId } from '@pages/dashboard/controllers/dashboardBlueprints.ts';
import { DASHBOARD_GRID_SETTINGS } from '@pages/dashboard/rendering/layout/constants.ts';
import type { DashboardEditionContribution } from '@core/edition/dashboardContribution.ts';

const resolveDashboardSectionTitle = (sectionId: DashboardBlueprintId, edition: DashboardEditionContribution | null): string => {
    switch (sectionId) {
        case 'status':
            return i18n.t('dashboard.sections.status.title');
        case 'logs':
            return i18n.t('dashboard.sections.logs.title');
        case 'plugins':
            return i18n.t('dashboard.sections.plugins.title');
        case 'models':
            return i18n.t('dashboard.sections.models.title');
        case 'hardwareWidgets':
            return i18n.t('dashboard.sections.hardwareWidgets.title');
        case 'network':
            return i18n.t('dashboard.sections.network.title');
        case 'storage':
            return i18n.t('dashboard.sections.storage.title');
        case 'imagecard':
            return i18n.t('dashboard.sections.imagecard.title');
        case 'memo':
            return i18n.t('dashboard.sections.memo.title');
        case 'requests':
            return i18n.t('dashboard.sections.requests.title');
        case 'productCapabilities':
            if (!edition) {
                throw new Error('Dashboard product capabilities title requires an edition contribution');
            }
            return edition.getTitle();
        case 'clock':
            return i18n.t('dashboard.sections.clock.title');
        case 'throughput':
            return i18n.t('dashboard.sections.throughput.title');
        case 'quickActions':
            return i18n.t('dashboard.sections.quickActions.title');
    }
    const unhandledSectionId: never = sectionId;
    return unhandledSectionId;
};

const resolveDashboardSectionSubtitle = (sectionId: DashboardBlueprintId, edition: DashboardEditionContribution | null): string => {
    switch (sectionId) {
        case 'status':
            return i18n.t('dashboard.sections.status.subtitle');
        case 'logs':
            return i18n.t('dashboard.sections.logs.subtitle');
        case 'plugins':
            return i18n.t('dashboard.sections.plugins.subtitle');
        case 'models':
            return i18n.t('dashboard.sections.models.subtitle');
        case 'hardwareWidgets':
            return i18n.t('dashboard.sections.hardwareWidgets.subtitle');
        case 'network':
            return i18n.t('dashboard.sections.network.subtitle');
        case 'storage':
            return i18n.t('dashboard.sections.storage.subtitle');
        case 'imagecard':
            return i18n.t('dashboard.sections.imagecard.subtitle');
        case 'memo':
            return i18n.t('dashboard.sections.memo.subtitle');
        case 'requests':
            return i18n.t('dashboard.sections.requests.subtitle');
        case 'productCapabilities':
            if (!edition) {
                throw new Error('Dashboard product capabilities subtitle requires an edition contribution');
            }
            return edition.getSubtitle();
        case 'clock':
            return i18n.t('dashboard.sections.clock.subtitle');
        case 'throughput':
            return i18n.t('dashboard.sections.throughput.subtitle');
        case 'quickActions':
            return i18n.t('dashboard.sections.quickActions.subtitle');
    }
    const unhandledSectionId: never = sectionId;
    return unhandledSectionId;
};

const createDashboardMovableLayoutConfig = (edition: DashboardEditionContribution | null = null): MovableSectionLayoutConfig<DashboardBlueprintId> => ({
    logLabel: 'DashboardLayout',
    gridSelector: '#dashboard-grid',
    sectionSelector: '.dashboard-section',
    sectionClassName: 'dashboard-section surface-card movable-section',
    sectionIdAttribute: 'data-section-id',
    dragHandleSelector: '[data-section-handle]',
    invalidDragSelector: '.section-controls',
    settings: DASHBOARD_GRID_SETTINGS,
    isSectionId: isDashboardBlueprintId,
    resolveTitle: (sectionId) => resolveDashboardSectionTitle(sectionId, edition),
    resolveSubtitle: (sectionId) => resolveDashboardSectionSubtitle(sectionId, edition)
});

export { createDashboardMovableLayoutConfig };
