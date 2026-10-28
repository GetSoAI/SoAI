/* SoAI - GPU apply-state refresh controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlApplyStateRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined } from '@core/typeGuards.ts';
import { GpuControlActionButtonsController, requiresGpuPrimaryActionRender } from '@pages/hardware/controllers/gpucontrol/GpuControlActionButtonsController.ts';
import { buildSettingsPayloadFromNormalized } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/payloads.ts';
import { hasPendingGpuApplyAction, resolveGpuPrimaryAction } from '@pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts';
import { computeApplyCapability } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/effects.ts';
import { GPU_CONTROL_TYPES, GPU_CONTROLS_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { clearGpuSlotPreview, clearTransientActionsForApplyChange } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlLifecycleManager.ts';
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
    isCertifiedRunLocked: (index: string | number) => boolean;
}

const refreshGpuApplyState = (context: GpuApplyStateRefreshContext, index: string | number): void => {
    if (isNullOrUndefined(index)) {
        return;
    }
    const key = String(index);
    const state = context.ensureGpuUiState(key);
    const snapshot = context.getSliderSnapshot(key);
    const readbackRecovered = state.previewSource === 'live' && GPU_CONTROL_TYPES.some((controlType) => snapshot[controlType].mode === null && state.liveSettings?.[GPU_CONTROLS_CONFIG[controlType].settingKey].mode != null);
    if (readbackRecovered) {
        context.renderGpuControls({ only: [key] });
        return;
    }
    const locked = context.isCertifiedRunLocked(key);
    const computedCapability = computeApplyCapability(context.gpuCapabilities, key, state, snapshot);
    state.applyCapability = computedCapability;
    state.canSaveCurrentSettings = hasGpuStorableSettings(buildSettingsPayloadFromNormalized(context.gpuCapabilities, key, computedCapability.normalized));
    GpuControlActionButtonsController({ index: key, snapshot, liveSettings: state.liveSettings, capabilities: context.gpuCapabilities?.[key] ?? null, capabilitiesByIndex: context.gpuCapabilities, pending: state.pending, locked, saveMode: state.saveMode, canStoreAppliedSettings: state.canStoreAppliedSettings, canSaveCurrentSettings: state.canSaveCurrentSettings, applyCapability: state.applyCapability, activeSlot: state.activeSlot, previewSlot: state.previewSlot, bootSlot: state.bootSlot });
    if (state.pending) return;
    const comparisonSettings = state.canStoreAppliedSettings ? computedCapability.normalized : state.liveSettings;
    syncGpuSliderChangeSurfaces(context.document, key, comparisonSettings, computedCapability.normalized, context.gpuCapabilities);
    if (computedCapability.mode === 'direct' && state.previewSlot) {
        clearGpuSlotPreview(state);
        state.applyCapability = computedCapability;
        context.renderGpuControls({ only: [key] });
        return;
    }
    const transientActionSync = state.previewSource === 'recovered' && state.saveMode ? 'none' : clearTransientActionsForApplyChange(state, hasPendingGpuApplyAction(state));
    if (transientActionSync === 'soaibench') {
        context.syncSoAIBenchUi({ only: [key] });
        return;
    }
    if (transientActionSync === 'render') {
        context.renderGpuControls({ only: [key] });
        return;
    }
    if (requiresGpuPrimaryActionRender(key, resolveGpuPrimaryAction(state), locked)) {
        context.renderGpuControls({ only: [key] });
        return;
    }
};

export { refreshGpuApplyState };
