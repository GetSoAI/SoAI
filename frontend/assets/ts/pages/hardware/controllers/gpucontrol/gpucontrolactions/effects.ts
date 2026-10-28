/* SoAI - Hardware page GPU control actions effects [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolactions/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { isCurrentGpuControlState } from '@pages/hardware/controllers/gpucontrol/gpuControlState.ts';
import type { TaskOptions } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS } from '@core/realtime/streammanager/resources/ids.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { buildDirectPayloadFromSnapshot, buildSlotStorePayloadFromSnapshot } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/payloads.ts';
import type { ControlContext, GpuApiCallContext, GpuApiCallOptions, GpuSnapshot } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/types.ts';
import { resolveGpuDisplayIndex } from '@pages/hardware/controllers/gpucontrol/gpuDisplayLabelManager.ts';
import { isGpuControlBackendMissingError, resolveGpuApiErrorCode, resolveGpuActionFailureMessage } from '@pages/hardware/controllers/gpucontrol/gpuControlErrors.ts';
import { gpuSettingStatesEqual, normalizeSnapshotForIndex } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import { commitGpuReset, clearSlotSaveMode, commitDirectApply, commitSlotApply } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlLifecycleManager.ts';
import { buildGpuResetPayload, hasGpuStorableSettings } from '@pages/hardware/controllers/gpucontrol/gpuControlValidation.ts';
import { GPU_SLIDER_CONFIG, GPU_CONTROLS_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';

const str = String;

const refreshGpuStreams = async (dependencies: GpuApiCallContext['dependencies']): Promise<void> => {
    const streamManager = await dependencies.resolveStreamManager();
    await Promise.all([streamManager.refresh(HARDWARE_GPU_SLOTS), streamManager.refresh(HARDWARE_GPU_CAPABILITIES)]);
};

const scheduleGpuStreamsRefresh = (dependencies: GpuApiCallContext['dependencies']): void => {
    void refreshGpuStreams(dependencies).catch((error) => {
        if (isAbortError(error)) return;
        const runtimeError = ensureError(error);
        errorHandler.error('HardwareGpuControl', 'GPU stream refresh failed after settings mutation', runtimeError);
    });
};

const gpuApiCall = async (context: GpuApiCallContext, index: string | number, { apiCall, onSuccess, onUnchanged, renderAfterSuccess }: GpuApiCallOptions): Promise<boolean> => {
    const key = str(index);
    let succeeded = false;
    const taskOptions: TaskOptions = {
        displayName: i18n.t('hardware.gpu.panelTitle'),
        telemetryContext: { gpuIndex: key },
        telemetryTags: ['hardware', 'gpu'],
        throwOnError: true,
        notifyOnError: true
    };
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
                    return;
                }
                if (result?.code === 'operation_cancelled' || result?.status === 'cancelled') return;
                scheduleGpuStreamsRefresh(context.dependencies);
                context.dependencies.showNotification(resolveGpuActionFailureMessage(result?.code), 'error');
            } catch (error) {
                if (isAbortError(error)) return;
                const runtimeError = ensureError(error);
                const code = resolveGpuApiErrorCode(runtimeError);
                if (code === 'operation_cancelled') return;
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
                scheduleGpuStreamsRefresh(context.dependencies);
                taskOptions.errorToastMessage = resolveGpuActionFailureMessage(code);
                throw runtimeError;
            }
        },
        taskOptions
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
            if (!isCurrentGpuControlState(context.ensureUiState(index), state, deviceId)) return;
            const normalized = normalizeSnapshotForIndex(context.capabilitiesByIndex, index, snapshot);
            context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.applied', { index: displayIndex }), 'success');
            commitDirectApply(state, normalized, snapshot, hasGpuStorableSettings(payload));
        },
        renderAfterSuccess: false
    });
};

const applyGpuSlot = async (context: ControlContext, deviceId: string, slot: string, boot: boolean | undefined, index: string | number): Promise<void> => {
    const displayIndex = resolveGpuDisplayIndex(context.capabilitiesByIndex, index);
    const state = context.ensureUiState(index);
    await gpuApiCall(context, index, {
        apiCall: () => context.dependencies.api.hardware.gpuSlots.apply(deviceId, slot, boot),
        onSuccess: () => {
            if (!isCurrentGpuControlState(context.ensureUiState(index), state, deviceId)) return;
            context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.slotApplied', { index: displayIndex, slot }), 'success');
            commitSlotApply(state, slot, isNullOrUndefined(boot) ? undefined : Boolean(boot));
        },
        renderAfterSuccess: true
    });
};

const resetGpuSettings = async (context: ControlContext, index: string | number, getSnapshot?: () => GpuSnapshot): Promise<void> => {
    const state = context.ensureUiState(index);
    if (state.pending || context.isCertifiedRunLocked(index)) {
        return;
    }
    const capabilities = context.capabilitiesByIndex?.[str(index)] ?? null;
    if (!capabilities || !state.deviceId) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.deviceMissing'), 'error');
        return;
    }
    const draft = getSnapshot ? normalizeSnapshotForIndex(context.capabilitiesByIndex, index, getSnapshot()) : state.previewSettings;
    const resetPayload = buildGpuResetPayload(capabilities, state.liveSettings);
    const draftResetPayload = buildGpuResetPayload(capabilities, draft);
    if (!resetPayload && !draftResetPayload) {
        context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.noSettings'), 'error');
        return;
    }
    if (!resetPayload) {
        for (const { type } of GPU_SLIDER_CONFIG) {
            if (draftResetPayload?.[GPU_CONTROLS_CONFIG[type].settingKey] === 'auto') context.setSliderToAuto(index, type);
        }
        commitGpuReset(state, {}, getSnapshot ? normalizeSnapshotForIndex(context.capabilitiesByIndex, index, getSnapshot()) : state.liveSettings);
        context.renderGpuControls({ only: [str(index)] });
        return;
    }
    const deviceId = state.deviceId;
    const displayIndex = resolveGpuDisplayIndex(context.capabilitiesByIndex, index);
    const isCurrentDevice = (): boolean => isCurrentGpuControlState(context.ensureUiState(index), state, deviceId);
    let resetChangedStructure = false;
    state.pending = true;
    try {
        context.refreshApplyState(index);
        await gpuApiCall(context, index, {
            apiCall: () => context.dependencies.api.hardware.gpuSettings.updateDevice(deviceId, resetPayload),
            onSuccess: () => {
                if (!isCurrentDevice()) return;
                const currentDraft = getSnapshot ? normalizeSnapshotForIndex(context.capabilitiesByIndex, index, getSnapshot()) : state.previewSettings;
                let retainedDraft = currentDraft;
                for (const { type } of GPU_SLIDER_CONFIG) {
                    const settingKey = GPU_CONTROLS_CONFIG[type].settingKey;
                    if ((resetPayload[settingKey] !== 'auto' && draftResetPayload?.[settingKey] !== 'auto') || (draft && currentDraft && !gpuSettingStatesEqual(draft[settingKey], currentDraft[settingKey]))) continue;
                    context.setSliderToAuto(index, type);
                    if (retainedDraft) retainedDraft = { ...retainedDraft, [settingKey]: { mode: 'auto', value: null } };
                }
                resetChangedStructure = state.saveMode || state.previewSlot !== null || state.showSoAIBenchActions;
                commitGpuReset(state, resetPayload, retainedDraft);
                context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.reset', { index: displayIndex }), 'success');
            },
            renderAfterSuccess: false
        });
    } finally {
        if (isCurrentDevice()) {
            state.pending = false;
            if (resetChangedStructure) context.renderGpuControls({ only: [str(index)] });
            else context.refreshApplyState(index);
        }
    }
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
                if (!isCurrentGpuControlState(context.ensureUiState(key), state, deviceId)) return;
                context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.slotSaved', { index: displayIndex, slot: slotId }), 'success');
                clearSlotSaveMode(state);
            },
            onUnchanged: () => {
                if (!isCurrentGpuControlState(context.ensureUiState(key), state, deviceId)) return;
                context.dependencies.showNotification(i18n.t('hardware.gpu.notifications.slotSaved', { index: displayIndex, slot: slotId }), 'success');
                clearSlotSaveMode(state);
            },
            renderAfterSuccess: true
        });
    } finally {
        if (isCurrentGpuControlState(context.ensureUiState(key), state, deviceId)) {
            state.pending = false;
            context.renderGpuControls({ only: [key] });
        }
    }
};

export { applyGpuSettingsDirect, applyGpuSlot, gpuApiCall, resetGpuSettings, saveGpuSlot };
