/* SoAI - Hardware page GPU control actions service [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolactions/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isCurrentGpuControlState } from '@pages/hardware/controllers/gpucontrol/gpuControlState.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { applyGpuSettingsDirect, applyGpuSlot, saveGpuSlot } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/effects.ts';
import type { ApplyCapabilityResult, ControlContext, GpuSnapshot } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/types.ts';
import { normalizeSlotSettings } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import { hasPendingGpuApplyAction } from '@pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts';
import { clearTransientActions } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlLifecycleManager.ts';
import { showGpuSoAIBenchHistory, showGpuSoAIBenchRun, startGpuSoAIBench, stopGpuSoAIBench } from '@pages/hardware/controllers/gpucontrol/soaibench/effects.ts';
import type { GpuSoAIBenchProfile } from '@pages/hardware/controllers/gpucontrol/soaibench/types.ts';

const str = String;

const handleGpuApplyClick = async (
    context: ControlContext,
    index: string | number,
    {
        getSnapshot,
        computeApplyCapability
    }: {
        getSnapshot: () => GpuSnapshot;
        computeApplyCapability: (snapshot: GpuSnapshot) => ApplyCapabilityResult;
    }
): Promise<void> => {
    if (isNullOrUndefined(index)) {
        return;
    }
    const key = str(index);
    const state = context.ensureUiState(key);
    if (state.pending || state.saveMode || context.isCertifiedRunLocked(key)) {
        return;
    }
    if (state.canStoreAppliedSettings) {
        return;
    }
    const snapshot = getSnapshot();
    const capability = computeApplyCapability(snapshot);
    if (!capability.canApply) {
        return;
    }
    if (!state.deviceId) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.deviceMissing'), 'error');
        return;
    }
    const deviceId = state.deviceId;
    state.pending = true;
    context.refreshApplyState(key);
    try {
        if (capability.mode === 'slot' && capability.slot) {
            await applyGpuSlot(context, deviceId, capability.slot, capability.applyAtBoot, key);
        } else {
            await applyGpuSettingsDirect(context, deviceId, snapshot, key);
        }
    } finally {
        if (isCurrentGpuControlState(context.ensureUiState(key), state, deviceId)) {
            state.pending = false;
            context.refreshApplyState(key);
        }
    }
};

const handleGpuSlotClick = async (context: ControlContext, index: string | number, slot: string | number, options: { snapshot: () => GpuSnapshot }): Promise<void> => {
    if (isNullOrUndefined(slot)) {
        return;
    }
    const key = str(index);
    const state = context.ensureUiState(key);
    if (!state.deviceId || state.pending || context.isCertifiedRunLocked(key)) {
        return;
    }
    const slotId = str(slot);
    if (state.saveMode) {
        await saveGpuSlot(context, key, slotId, options.snapshot());
        return;
    }

    const slotMetadata = context.getSlotEntryByIndex(index);
    const recovered = slotId.startsWith('recovered/') ? slotMetadata?.reconciliation?.recoveredProfiles.find((profile) => profile.id === slotId.slice('recovered/'.length)) : null;
    const slotData = recovered ? recovered.profile : slotMetadata?.slots?.[slotId];
    const settings = slotData?.settings;
    if (!settings) {
        return;
    }
    state.previewSlot = recovered ? null : slotId;
    state.previewSource = recovered ? 'recovered' : 'slot';
    state.previewSettings = normalizeSlotSettings(settings, slotData?.fieldModes ?? null);
    state.previewHydrated = false;
    state.bootToggleDirty = false;
    state.canStoreAppliedSettings = false;
    clearTransientActions(state);
    if (recovered) state.saveMode = true;
    const boot = slotMetadata?.boot;
    state.applyAtBootDesired = Boolean(boot?.enabled && str(boot.slot) === slotId);
    context.renderGpuControls({ only: [key] });
};

const handleGpuSoAIBenchStartClick = async (context: ControlContext, index: string | number, profile: GpuSoAIBenchProfile): Promise<void> => {
    if (isNullOrUndefined(index)) {
        return;
    }
    const key = str(index);
    const state = context.ensureUiState(key);
    if (state.pending || state.saveMode || hasPendingGpuApplyAction(state) || context.isCertifiedRunLocked(key)) {
        return;
    }
    if (!state.deviceId) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.deviceMissing'), 'error');
        return;
    }
    const deviceId = state.deviceId;
    state.pending = true;
    state.soaibenchStopRequested = false;
    context.syncSoAIBenchUi({ only: [key] });
    try {
        await startGpuSoAIBench(context, deviceId, key, profile);
    } finally {
        if (isCurrentGpuControlState(context.ensureUiState(key), state, deviceId)) {
            state.pending = false;
            context.syncSoAIBenchUi({ only: [key] });
        }
    }
};

const handleGpuSoAIBenchStopClick = async (context: ControlContext, index: string | number): Promise<void> => {
    if (isNullOrUndefined(index)) {
        return;
    }
    const key = str(index);
    const state = context.ensureUiState(key);
    if (state.pending) {
        return;
    }
    if (!state.deviceId) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.deviceMissing'), 'error');
        return;
    }
    const deviceId = state.deviceId;
    state.pending = true;
    state.soaibenchStopRequested = true;
    context.syncSoAIBenchUi({ only: [key] });
    try {
        await stopGpuSoAIBench(context, deviceId, key);
    } catch (error) {
        if (isCurrentGpuControlState(context.ensureUiState(key), state, deviceId)) state.soaibenchStopRequested = false;
        throw error;
    } finally {
        if (isCurrentGpuControlState(context.ensureUiState(key), state, deviceId)) {
            state.pending = false;
            context.syncSoAIBenchUi({ only: [key] });
        }
    }
};

const handleGpuSoAIBenchHistoryClick = async (context: ControlContext, index: string | number): Promise<void> => {
    if (isNullOrUndefined(index)) {
        return;
    }
    const key = str(index);
    const state = context.ensureUiState(key);
    if (!state.deviceId) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.deviceMissing'), 'error');
        return;
    }
    await showGpuSoAIBenchHistory(context, state.deviceId, key);
};

const handleGpuSoAIBenchRunClick = async (context: ControlContext, index: string | number): Promise<void> => {
    if (isNullOrUndefined(index)) {
        return;
    }
    const key = str(index);
    const state = context.ensureUiState(key);
    if (!state.deviceId) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.deviceMissing'), 'error');
        return;
    }
    await showGpuSoAIBenchRun(context, state.deviceId, key);
};

export { handleGpuApplyClick, handleGpuSlotClick, handleGpuSoAIBenchHistoryClick, handleGpuSoAIBenchRunClick, handleGpuSoAIBenchStartClick, handleGpuSoAIBenchStopClick };
