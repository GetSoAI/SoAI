/* SoAI - GPU control manager adapters [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ControlContext } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/types.ts';
import type { GpuControlManagerViewContext } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/internalContracts.ts';
import type { GpuControlTelemetry } from '@pages/hardware/controllers/gpucontrol/gpuControlTelemetryController.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuControlManagerDependencies, GpuSlotEntry, GpuUiState, SecurityService, SliderElements } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

interface BuildGpuControlManagerViewContextDependencies {
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

interface BuildGpuControlDomContextDependencies {
    dependencies: GpuControlManagerDependencies;
    capabilitiesByIndex: GpuCapabilitiesByIndex | null;
    ensureUiState: (index: string | number) => GpuUiState;
    refreshApplyState: (index: string | number) => void;
}

interface BuildGpuControlActionContextDependencies {
    dependencies: GpuControlManagerDependencies;
    capabilitiesByIndex: GpuCapabilitiesByIndex | null;
    ensureUiState: (index: string | number) => GpuUiState;
    renderGpuControls: (options?: { only?: string[] | null }) => void;
    syncSoAIBenchUi: (options?: { only?: string[] | null }) => void;
    getSlotEntryByIndex: (index: string | number) => GpuSlotEntry | null;
    setSliderToAuto: (index: string | number, controlType: string) => void;
    setSliderToManual: (index: string | number, controlType: string, manualValue: string | number | null) => void;
    refreshApplyState: (index: string | number) => void;
}

const buildGpuControlManagerViewContext = (dependencies: BuildGpuControlManagerViewContextDependencies): GpuControlManagerViewContext => {
    return {
        dependencies: dependencies.dependencies,
        security: dependencies.security,
        capabilitiesByIndex: dependencies.capabilitiesByIndex,
        telemetryByDeviceId: dependencies.telemetryByDeviceId,
        soaibenchRuns: dependencies.soaibenchRuns,
        ensureUiState: dependencies.ensureUiState,
        refreshApplyState: dependencies.refreshApplyState,
        setSliderToAuto: dependencies.setSliderToAuto,
        setSliderToManual: dependencies.setSliderToManual,
        getSliderElements: dependencies.getSliderElements
    };
};

const buildGpuControlDomContext = (dependencies: BuildGpuControlDomContextDependencies): { document: Document; capabilitiesByIndex: GpuCapabilitiesByIndex | null; ensureUiState: (index: string | number) => GpuUiState; refreshApplyState: (index: string | number) => void } => {
    return {
        document: dependencies.dependencies.dom.getDocument(),
        capabilitiesByIndex: dependencies.capabilitiesByIndex,
        ensureUiState: dependencies.ensureUiState,
        refreshApplyState: dependencies.refreshApplyState
    };
};

const buildGpuControlActionContext = (dependencies: BuildGpuControlActionContextDependencies): ControlContext => {
    return {
        dependencies: dependencies.dependencies,
        capabilitiesByIndex: dependencies.capabilitiesByIndex,
        ensureUiState: dependencies.ensureUiState,
        renderGpuControls: dependencies.renderGpuControls,
        syncSoAIBenchUi: dependencies.syncSoAIBenchUi,
        getSlotEntryByIndex: dependencies.getSlotEntryByIndex,
        setSliderToAuto: dependencies.setSliderToAuto,
        setSliderToManual: dependencies.setSliderToManual,
        refreshApplyState: dependencies.refreshApplyState
    };
};

export { buildGpuControlActionContext, buildGpuControlDomContext, buildGpuControlManagerViewContext };
