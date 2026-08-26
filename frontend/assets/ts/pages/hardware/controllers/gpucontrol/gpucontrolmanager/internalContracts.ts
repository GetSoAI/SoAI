/* SoAI - Hardware page internal contracts [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { GpuControlTelemetry } from '@pages/hardware/controllers/gpucontrol/gpuControlTelemetryController.ts';
import type { GpuCapabilities, GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuControlManagerDependencies, GpuUiState, SecurityService, SliderElements } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

export interface GpuControlManagerViewContext {
    dependencies: GpuControlManagerDependencies;
    security: SecurityService;
    capabilitiesByIndex: GpuCapabilitiesByIndex | null;
    telemetryByDeviceId: Map<string, GpuControlTelemetry>;
    soaibenchRuns: JsonValue | null;
    ensureUiState: (index: string | number) => GpuUiState;
    refreshApplyState: (index: string | number) => void;
    setSliderToAuto: (index: string | number, type: string, explicitDefault?: string | number | null, options?: { preserveManual?: boolean }) => void;
    setSliderToManual: (index: string | number, type: string, manualValue?: string | number | null) => void;
    getSliderElements: (index: string | number, type: string) => SliderElements;
}

export interface GpuControlManagerRendererContext {
    security: SecurityService;
    getIconSync: GpuControlManagerDependencies['getIconSync'];
    capabilitiesByIndex: GpuCapabilitiesByIndex | null;
    telemetryByDeviceId: Map<string, GpuControlTelemetry>;
    soaibenchRuns: JsonValue | null;
    ensureUiState: (index: string | number) => GpuUiState;
}

export interface GpuControlManagerRenderPanelContext {
    renderer: GpuControlManagerRendererContext;
    index: string;
    caps: GpuCapabilities;
}

export interface GpuControlSnapshotControlState {
    isAuto: boolean;
    value: string;
    lastManual: string | null;
}

export interface GpuControlSnapshotEntry {
    deviceId: string | null;
    controls: Record<string, GpuControlSnapshotControlState>;
}

export type GpuControlViewSnapshot = Record<string, GpuControlSnapshotEntry>;
