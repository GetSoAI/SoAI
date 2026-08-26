/* SoAI - Hardware page GPU control actions effects [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolactions/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS } from '@core/realtime/streammanager/resources/ids.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { buildDirectPayloadFromSnapshot, buildSlotStorePayloadFromSnapshot } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/payloads.ts';
import type { ControlContext, GpuApiCallContext, GpuApiCallOptions, GpuSnapshot } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/types.ts';
import { resolveGpuDisplayIndex } from '@pages/hardware/controllers/gpucontrol/gpuDisplayLabelManager.ts';
import { isGpuControlBackendMissingError, resolveGpuApiErrorCode } from '@pages/hardware/controllers/gpucontrol/gpuControlErrors.ts';
import { normalizeSnapshotForIndex } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import { clearSlotSaveMode, commitDirectApply, commitSlotApply } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlLifecycleManager.ts';
import { buildGpuResetPayload, hasGpuStorableSettings } from '@pages/hardware/controllers/gpucontrol/gpuControlValidation.ts';

const str = String;

const refreshGpuStreams = async (dependencies: GpuApiCallContext['dependencies']): Promise<void> => {
    const streamManager = await dependencies.resolveStreamManager();
    await Promise.all([streamManager.refresh(HARDWARE_GPU_SLOTS), streamManager.refresh(HARDWARE_GPU_CAPABILITIES)]);
};

const scheduleGpuStreamsRefresh = (dependencies: GpuApiCallContext['dependencies']): void => {
    void refreshGpuStreams(dependencies).catch((error) => {
        const runtimeError = ensureError(error);
        errorHandler.error('HardwareGpuControl', 'GPU stream refresh failed after settings mutation', runtimeError);
    });
};

const gpuApiCall = async (context: GpuApiCallContext, index: string | number, { apiCall, onSuccess, onUnchanged, renderAfterSuccess }: GpuApiCallOptions): Promise<boolean> => {
    const key = str(index);
    let succeeded = false;
    await context.dependencies.runPageTask(
        'hardware.gpu.action',
        async () => {
            try {
                const result = await apiCall();
                if (result?.success) {
                    await onSuccess(result);
                    scheduleGpuStreamsRefresh(context.dependencies);
                    succeeded = true;
                    return;
                }
                if (result?.code === 'slot_unchanged') {
                    await onUnchanged?.();
                    scheduleGpuStreamsRefresh(context.dependencies);
                    succeeded = true;
                }
            } catch (error) {
                const runtimeError = ensureError(error);
                const code = resolveGpuApiErrorCode(runtimeError);
                if (code === 'slot_unchanged') {
                    await onUnchanged?.();
                    scheduleGpuStreamsRefresh(context.dependencies);
                    succeeded = true;
                    return;
                }
                if (isGpuControlBackendMissingError(runtimeError)) {
                    scheduleGpuStreamsRefresh(context.dependencies);
                    context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.controlBackendMissing'), 'error');
                    return;
                }
                throw runtimeError;
            }
        },
        {
            displayName: i18n.t('hardware.gpu.panelTitle'),
            telemetryContext: { gpuIndex: key },
            telemetryTags: ['hardware', 'gpu'],
            throwOnError: true,
            notifyOnError: true
        }
    );
    if (renderAfterSuccess) {
        context.renderGpuControls({ only: [key] });
    }
    return succeeded;
};

const applyGpuSettingsDirect = async (context: ControlContext, deviceId: string, snapshot: GpuSnapshot, index: string | number): Promise<void> => {
    const displayIndex = resolveGpuDisplayIndex(context.capabilitiesByIndex, index);
    const state = context.ensureUiState(index);
    const payload = buildDirectPayloadFromSnapshot(context.capabilitiesByIndex, index, snapshot, state.liveSettings);
    await gpuApiCall(context, index, {
        apiCall: () => context.dependencies.api.hardware.gpuSettings.updateDevice(deviceId, payload),
        onSuccess: () => {
            const normalized = normalizeSnapshotForIndex(context.capabilitiesByIndex, index, snapshot);
            context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.applied', { index: displayIndex }), 'success');
            commitDirectApply(state, normalized, snapshot, hasGpuStorableSettings(payload));
        },
        renderAfterSuccess: false
    });
};

const applyGpuSlot = async (context: ControlContext, deviceId: string, slot: string, boot: boolean | undefined, index: string | number): Promise<void> => {
    const displayIndex = resolveGpuDisplayIndex(context.capabilitiesByIndex, index);
    await gpuApiCall(context, index, {
        apiCall: () => context.dependencies.api.hardware.gpuSlots.apply(deviceId, slot, boot),
        onSuccess: () => {
            const state = context.ensureUiState(index);
            context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.slotApplied', { index: displayIndex, slot }), 'success');
            commitSlotApply(state, slot, isNullOrUndefined(boot) ? undefined : Boolean(boot));
        },
        renderAfterSuccess: false
    });
};

const resetGpuSettings = async (context: ControlContext, index: string | number): Promise<void> => {
    const capabilities = context.capabilitiesByIndex?.[str(index)] ?? null;
    const state = context.ensureUiState(index);
    if (!capabilities || !state.deviceId) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.deviceMissing'), 'error');
        return;
    }
    const resetPayload = buildGpuResetPayload(capabilities);
    if (!resetPayload) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.noSettings'), 'error');
        return;
    }
    const deviceId = state.deviceId;
    const displayIndex = resolveGpuDisplayIndex(context.capabilitiesByIndex, index);
    await gpuApiCall(context, index, {
        apiCall: () => context.dependencies.api.hardware.gpuSettings.updateDevice(deviceId, resetPayload),
        onSuccess: () => {
            context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.reset', { index: displayIndex }), 'success');
            state.previewSlot = null;
            state.previewSettings = null;
            state.previewSource = 'live';
            state.applyAtBootDesired = false;
            state.bootToggleDirty = false;
            state.canStoreAppliedSettings = false;
            state.saveMode = false;
            state.showSoAIBenchActions = false;
            context.resetUiControls?.(index);
        },
        renderAfterSuccess: true
    });
};

const saveGpuSlot = async (context: ControlContext, index: string | number, slotId: string, snapshot: GpuSnapshot): Promise<void> => {
    const key = str(index);
    const state = context.ensureUiState(key);
    if (!state.deviceId) {
        return;
    }
    const deviceId = state.deviceId;
    const displayIndex = resolveGpuDisplayIndex(context.capabilitiesByIndex, key);
    const payload = buildSlotStorePayloadFromSnapshot(context.capabilitiesByIndex, key, snapshot);
    if (!hasGpuStorableSettings(payload.settings)) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.noManualChange'), 'info');
        return;
    }
    state.pending = true;
    context.renderGpuControls({ only: [key] });
    try {
        await gpuApiCall(context, key, {
            apiCall: () => context.dependencies.api.hardware.gpuSlots.store(deviceId, slotId, payload),
            onSuccess: async () => {
                context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.slotSaved', { index: displayIndex, slot: slotId }), 'success');
                clearSlotSaveMode(state);
            },
            onUnchanged: () => {
                context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.slotSaved', { index: displayIndex, slot: slotId }), 'success');
                clearSlotSaveMode(state);
            },
            renderAfterSuccess: true
        });
    } finally {
        state.pending = false;
        context.renderGpuControls({ only: [key] });
    }
};

export { applyGpuSettingsDirect, applyGpuSlot, gpuApiCall, resetGpuSettings, saveGpuSlot };
