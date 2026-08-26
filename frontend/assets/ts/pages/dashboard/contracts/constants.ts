/* SoAI - Dashboard page contracts constants [frontend/assets/ts/pages/dashboard/contracts/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { HARDWARE, METRICS, MODELS, PLUGINS, STATUS } from '@core/realtime/streammanager/resources/ids.ts';
import type { DashboardLiveDataKey, DashboardSectionId } from '@pages/dashboard/controllers/dashboardLiveData.ts';
import { isStatusManagerContract, type StatusManagerContract } from '@pages/dashboard/contracts/statusManager.ts';

const DASHBOARD_SECTION_RENDER_ORDER: readonly DashboardSectionId[] = Object.freeze(['status', 'productCapabilities', 'requests', 'plugins', 'models', 'hardwareWidgets', 'network', 'storage']);

const DASHBOARD_REQUIRED_STREAMS: ReadonlyArray<{
    resource: string;
    key: DashboardLiveDataKey;
}> = Object.freeze([
    { resource: STATUS, key: 'status' },
    { resource: METRICS, key: 'metrics' },
    { resource: HARDWARE, key: 'hardware' },
    { resource: PLUGINS, key: 'plugins' },
    { resource: MODELS, key: 'models' }
]);

const PAGE_ID = 'dashboard';
const PAGE_MODULE_ID = 'pages.DashboardPage';

export { DASHBOARD_REQUIRED_STREAMS, DASHBOARD_SECTION_RENDER_ORDER, PAGE_ID, PAGE_MODULE_ID, isStatusManagerContract };
export type { DashboardLiveDataKey, DashboardSectionId, StatusManagerContract };
