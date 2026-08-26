/* SoAI - Hardware page GPU control actions contracts [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolactions/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuControlManagerDependencies, GpuSettingsState, GpuSettingsUpdatePayload, GpuSlotEntry, GpuSlotStorePayload, GpuSnapshot, GpuUiState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

type ControlContext = {
    dependencies: Pick<GpuControlManagerDependencies, 'api' | 'resolveStreamManager' | 'runPageTask' | 'showNotification' | 'showSoAIBenchHistory' | 'showSoAIBenchRun'>;
    capabilitiesByIndex: GpuCapabilitiesByIndex | null;
    ensureUiState: (index: string | number) => GpuUiState;
    renderGpuControls: (options?: { only?: string[] | null }) => void;
    syncSoAIBenchUi: (options?: { only?: string[] | null }) => void;
    getSlotEntryByIndex: (index: string | number) => GpuSlotEntry | null;
    setSliderToAuto: (index: string | number, controlType: string) => void;
    setSliderToManual: (index: string | number, controlType: string, manualValue: string | number | null) => void;
    refreshApplyState: (index: string | number) => void;
    resetUiControls?: (index: string | number) => void;
};

type GpuApiCallContext = Pick<ControlContext, 'dependencies' | 'renderGpuControls'>;

interface GpuApiCallOptions {
    apiCall: () => Promise<GpuOperationResponse>;
    onSuccess: (response: GpuOperationResponse) => void | Promise<void>;
    onUnchanged?: () => void | Promise<void>;
    renderAfterSuccess: boolean;
}

interface ApplyCapabilityResult {
    canApply: boolean;
    mode: 'direct' | 'slot';
    slot: string | null;
    applyAtBoot?: boolean;
}

export type { ApplyCapabilityResult, ControlContext, GpuApiCallContext, GpuApiCallOptions, GpuSettingsState, GpuSettingsUpdatePayload, GpuSlotStorePayload, GpuSnapshot };
