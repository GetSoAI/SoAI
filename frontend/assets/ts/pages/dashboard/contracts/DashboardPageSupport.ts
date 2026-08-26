/* SoAI - Dashboard page support [frontend/assets/ts/pages/dashboard/contracts/DashboardPageSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { FirstRunModalService } from '@core/firstrun/protocols.ts';
import type { LogStream } from '@features/logging/public.ts';
import { DASHBOARD_REQUIRED_STREAMS } from '@pages/dashboard/contracts/constants.ts';
import type { DashboardEditionContribution } from '@core/edition/dashboardContribution.ts';

const dashboardLogger = createModuleLogger('DashboardPage', { defaultLevel: 'warn' });
const DASHBOARD_REQUIRED_RESOURCES = Object.freeze(DASHBOARD_REQUIRED_STREAMS.map(({ resource }) => resource));
const DASHBOARD_REQUIRED_RESOURCES_FOR_READY = Object.freeze(DASHBOARD_REQUIRED_RESOURCES.slice(0, 4));
interface DashboardPageDependencies {
    firstRunModals: FirstRunModalService;
    logStream: LogStream;
    edition: DashboardEditionContribution | null;
}

export { dashboardLogger, DASHBOARD_REQUIRED_RESOURCES, DASHBOARD_REQUIRED_RESOURCES_FOR_READY };
export type { DashboardPageDependencies };
