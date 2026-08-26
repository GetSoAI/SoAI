/* SoAI - GPU apply-state refresh controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlApplyStateRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined } from '@core/typeGuards.ts';
import { GpuControlActionButtonsController, requiresGpuPrimaryActionRender } from '@pages/hardware/controllers/gpucontrol/GpuControlActionButtonsController.ts';
import { buildSettingsPayloadFromNormalized } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/payloads.ts';
import { hasPendingGpuApplyAction, resolveGpuPrimaryAction } from '@pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts';
import { computeApplyCapability } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/effects.ts';
import { clearSlotPreviewForDirectEdit, clearTransientActionsForApplyChange } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlLifecycleManager.ts';
import { syncGpuSliderChangeSurfaces } from '@pages/hardware/controllers/gpucontrol/gpuControlDirtySurfacesController.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuSnapshot, GpuUiState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';
import { hasGpuStorableSettings } from '@pages/hardware/controllers/gpucontrol/gpuControlValidation.ts';

interface GpuApplyStateRefreshContext {
    document: Document;
    gpuCapabilities: GpuCapabilitiesByIndex | null;
    ensureGpuUiState: (index: string | number) => GpuUiState;
    getSliderSnapshot: (index: string | number) => GpuSnapshot;
    renderGpuControls: (options: { only?: string[] | null }) => void;
    syncSoAIBenchUi: (options: { only?: string[] | null }) => void;
    updateHeaderSaveAction: () => void;
}

const refreshGpuApplyState = (context: GpuApplyStateRefreshContext, index: string | number): void => {
    if (isNullOrUndefined(index)) {
        return;
    }
    const key = String(index);
    const state = context.ensureGpuUiState(key);
    const snapshot = context.getSliderSnapshot(key);
    const computedCapability = computeApplyCapability(context.gpuCapabilities, key, state, snapshot);
    state.applyCapability = computedCapability;
    state.canSaveCurrentSettings = hasGpuStorableSettings(buildSettingsPayloadFromNormalized(context.gpuCapabilities, key, computedCapability.normalized));
    GpuControlActionButtonsController({ index: key, snapshot, pending: state.pending, saveMode: state.saveMode, canStoreAppliedSettings: state.canStoreAppliedSettings, canSaveCurrentSettings: state.canSaveCurrentSettings, applyCapability: state.applyCapability, activeSlot: state.activeSlot, previewSlot: state.previewSlot, bootSlot: state.bootSlot });
    const comparisonSettings = state.canStoreAppliedSettings ? computedCapability.normalized : state.liveSettings;
    syncGpuSliderChangeSurfaces(context.document, key, comparisonSettings, computedCapability.normalized);
    if (computedCapability.mode === 'direct' && state.previewSlot) {
        clearSlotPreviewForDirectEdit(state);
        state.applyCapability = computedCapability;
        context.renderGpuControls({ only: [key] });
        context.updateHeaderSaveAction();
        return;
    }
    const transientActionSync = clearTransientActionsForApplyChange(state, hasPendingGpuApplyAction(state));
    if (transientActionSync === 'soaibench') {
        context.syncSoAIBenchUi({ only: [key] });
        context.updateHeaderSaveAction();
        return;
    }
    if (transientActionSync === 'render') {
        context.renderGpuControls({ only: [key] });
        context.updateHeaderSaveAction();
        return;
    }
    if (requiresGpuPrimaryActionRender(key, resolveGpuPrimaryAction(state))) {
        context.renderGpuControls({ only: [key] });
        context.updateHeaderSaveAction();
        return;
    }
    context.updateHeaderSaveAction();
};

export { refreshGpuApplyState };
