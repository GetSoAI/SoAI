/* SoAI - Dashboard page rendering [frontend/assets/ts/pages/dashboard/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export const renderDashboardPageView = (dependencies: { columns: number }): string => {
    return ['<div id="dashboard-root" class="dashboard-container page-scrollable" data-section="dashboard" data-page-transition-surface="true">', `<div id="dashboard-grid" class="dashboard-grid movable-sections-grid" data-columns="${dependencies.columns}"></div>`, '<div id="grid-overlay" class="grid-overlay u-hidden"></div>', '</div>'].join('');
};
