/* SoAI - Hardware page layout contracts [frontend/assets/ts/pages/hardware/rendering/layout/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MovablePanelBlueprint } from '@core/routing/pages/movablesections/panelLayoutController.ts';

type HardwarePanelId = 'widgets' | 'history' | 'gpuControls' | 'processes' | 'network' | 'storage' | 'memorySwap';

type HardwarePanelBlueprint = MovablePanelBlueprint;

interface HardwareLayoutPermissions {
    canTuneGpu: boolean;
    canViewProcesses: boolean;
}

export type { HardwareLayoutPermissions, HardwarePanelBlueprint, HardwarePanelId };
