/* SoAI - Dashboard page controllers contracts [frontend/assets/ts/pages/dashboard/controllers/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareData, HardwareSnapshot } from '@features/hardware/public.ts';
import type { DashboardHost } from '@core/edition/dashboardContribution.ts';

interface DashboardHardwareStateAccess {
    hasHardware: () => boolean;
    getRawHardwareSnapshot: () => HardwareSnapshot | HardwareData | null;
}

interface DashboardHardwareSectionsControllerDependencies {
    host: DashboardHost;
    state: DashboardHardwareStateAccess;
    isDestroyed: () => boolean;
}

interface DashboardHardwareSectionsRenderContext {
    host: DashboardHost;
    state: DashboardHardwareStateAccess;
    isDestroyed: () => boolean;
}

export type { DashboardHardwareSectionsControllerDependencies, DashboardHardwareSectionsRenderContext, DashboardHardwareStateAccess };
