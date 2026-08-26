/* SoAI - Dashboard page DOM contracts [frontend/assets/ts/pages/dashboard/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DashboardUiRefs } from '@pages/dashboard/types.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type DashboardDomDependencies = PageDomOwnerHost;

export const requireDashboardRoot = (dependencies: DashboardDomDependencies): HTMLElement => dependencies.pageDom.requireHTMLElement('#dashboard-root');
export const optionalDashboardRoot = (dependencies: DashboardDomDependencies): HTMLElement | null => dependencies.pageDom.optionalHTMLElement('#dashboard-root');

export const requireDashboardUi = (dependencies: DashboardDomDependencies): DashboardUiRefs => {
    const root = requireDashboardRoot(dependencies);
    const grid = dependencies.pageDom.requireHTMLElement('#dashboard-grid', root);
    const overlay = dependencies.pageDom.requireHTMLElement('#grid-overlay', root);
    return { root, grid, overlay };
};

export const optionalDashboardMainStateIndicator = (dependencies: DashboardDomDependencies): Element | null => {
    const root = requireDashboardRoot(dependencies);
    return dependencies.pageDom.optionalHTMLElement('#status-main-state', root);
};
