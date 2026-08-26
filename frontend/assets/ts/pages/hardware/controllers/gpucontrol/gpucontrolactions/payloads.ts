/* SoAI - Hardware page payloads [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolactions/payloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined } from '@core/typeGuards.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import type { ControlContext, GpuSettingsState, GpuSettingsUpdatePayload, GpuSlotStorePayload, GpuSnapshot } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/types.ts';
import { isGpuSettingSupported } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts';
import { GPU_CONTROL_TYPES, GPU_CONTROLS_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { gpuSettingStatesEqual, normalizeSlotSettings, normalizeSnapshotForIndex } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import type { GpuSettingKey } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const str = String;

const toStrictInt = (value: number | null): number | null => {
    const numeric = readCoercedFiniteNumberOrNullValue(value);
    if (numeric === null) return null;
    return Number.isInteger(numeric) ? numeric : Math.round(numeric);
};

const buildSettingsPayload = (capabilitiesByIndex: ControlContext['capabilitiesByIndex'], index: string | number, normalized: GpuSettingsState, baseline: GpuSettingsState | null): GpuSettingsUpdatePayload => {
    const payload: GpuSettingsUpdatePayload = {};
    const assign = (key: GpuSettingKey): void => {
        if (!isGpuSettingSupported(capabilitiesByIndex, index, key)) {
            return;
        }
        const setting = normalized[key];
        if (baseline && gpuSettingStatesEqual(setting, baseline[key])) {
            return;
        }
        if (setting.mode === 'auto') {
            payload[key] = 'auto';
            return;
        }
        const numeric = toStrictInt(setting.value);
        if (numeric === null) {
            return;
        }
        payload[key] = numeric;
    };
    assign('powerLimit');
    assign('fanSpeed');
    assign('coreClock');
    assign('memClock');
    return payload;
};

const buildFieldModesPayload = (capabilitiesByIndex: ControlContext['capabilitiesByIndex'], index: string | number, normalized: GpuSettingsState): GpuSlotStorePayload['fieldModes'] => {
    const fieldModes: GpuSlotStorePayload['fieldModes'] = {};
    const assign = (key: GpuSettingKey): void => {
        if (!isGpuSettingSupported(capabilitiesByIndex, index, key)) {
            return;
        }
        const setting = normalized[key];
        fieldModes[key] = setting.mode;
    };
    assign('powerLimit');
    assign('fanSpeed');
    assign('coreClock');
    assign('memClock');
    return fieldModes;
};

const buildDirectPayloadFromSnapshot = (capabilitiesByIndex: ControlContext['capabilitiesByIndex'], index: string | number, snapshot: GpuSnapshot, liveSettings: GpuSettingsState | null): GpuSettingsUpdatePayload => {
    return buildSettingsPayload(capabilitiesByIndex, index, normalizeSnapshotForIndex(capabilitiesByIndex, index, snapshot), liveSettings);
};

const buildSettingsPayloadFromNormalized = (capabilitiesByIndex: ControlContext['capabilitiesByIndex'], index: string | number, normalized: GpuSettingsState): GpuSettingsUpdatePayload => {
    return buildSettingsPayload(capabilitiesByIndex, index, normalized, null);
};

const buildSlotStorePayloadFromSnapshot = (capabilitiesByIndex: ControlContext['capabilitiesByIndex'], index: string | number, snapshot: GpuSnapshot): GpuSlotStorePayload => {
    const normalized = normalizeSnapshotForIndex(capabilitiesByIndex, index, snapshot);
    return {
        settings: buildSettingsPayload(capabilitiesByIndex, index, normalized, null),
        fieldModes: buildFieldModesPayload(capabilitiesByIndex, index, normalized)
    };
};

const applySlotToControls = (context: Pick<ControlContext, 'setSliderToAuto' | 'setSliderToManual'>, index: string | number, normalized: ReturnType<typeof normalizeSlotSettings>): void => {
    GPU_CONTROL_TYPES.forEach((controlType) => {
        const config = GPU_CONTROLS_CONFIG[controlType];
        const setting = normalized[config.settingKey];
        if (setting.mode === 'auto') {
            context.setSliderToAuto(index, controlType);
            return;
        }
        context.setSliderToManual(index, controlType, setting.value ?? 0);
    });
};

const handleGpuBootToggle = (context: Pick<ControlContext, 'ensureUiState' | 'renderGpuControls' | 'refreshApplyState'>, index: string | number, enabled: boolean): void => {
    if (isNullOrUndefined(index)) {
        return;
    }
    const key = str(index);
    const state = context.ensureUiState(key);
    if (!state.previewSlot) {
        context.renderGpuControls({ only: [key] });
        return;
    }
    const desired = Boolean(enabled);
    const slotMetadata = state.slotMetadata;
    const live = slotMetadata?.live;
    const boot = slotMetadata?.boot;
    const liveBootEnabled = Boolean(live?.bootEnabled);
    const liveBootSlot = live?.bootSlot ?? null;
    const bootEnabled = Boolean(boot?.enabled);
    const bootSlot = boot?.slot ?? null;
    const isLive = liveBootEnabled && str(liveBootSlot) === state.previewSlot;
    const isSaved = !isLive && bootEnabled && str(bootSlot) === state.previewSlot;
    state.applyAtBootDesired = desired;
    state.bootToggleDirty = desired !== (isLive || isSaved);
    context.refreshApplyState(key);
};

export { applySlotToControls, buildDirectPayloadFromSnapshot, buildSettingsPayloadFromNormalized, buildSlotStorePayloadFromSnapshot, handleGpuBootToggle };
