/* SoAI - Dashboard page controllers state [frontend/assets/ts/pages/dashboard/controllers/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { HardwareWidgetManager, type HardwareData, type HardwareSnapshot } from '@features/hardware/public.ts';

interface DashboardHardwareWidgetsManagerState {
    hardwareWidgetsManager: HardwareWidgetManager | null;
    hardwareWidgetsInitialized: boolean;
    hardwareWidgetsInitializePromise: Promise<void> | null;
    hardwareWidgetsPendingSnapshot: HardwareSnapshot | HardwareData | null;
}

const createDashboardHardwareWidgetsManagerState = (): DashboardHardwareWidgetsManagerState => ({
    hardwareWidgetsManager: null,
    hardwareWidgetsInitialized: false,
    hardwareWidgetsInitializePromise: null,
    hardwareWidgetsPendingSnapshot: null
});

export type { DashboardHardwareWidgetsManagerState };
export { createDashboardHardwareWidgetsManagerState };
