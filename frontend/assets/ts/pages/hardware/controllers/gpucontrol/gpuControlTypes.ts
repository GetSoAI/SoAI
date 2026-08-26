/* SoAI - Hardware page GPU control types [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { GpuSlotDevice } from '@core/types/streamTypes.ts';
import type { GpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { SoAIBenchHistoryOpenRequest, SoAIBenchRunOpenRequest } from '@features/hardware/public.ts';
import type { GpuSoAIBenchRunLookupPayload, GpuSoAIBenchStartPayload } from '@pages/hardware/controllers/gpucontrol/soaibench/types.ts';

export type GpuControlType = 'power' | 'core' | 'memory' | 'fan';
export type GpuSettingKey = 'powerLimit' | 'coreClock' | 'memClock' | 'fanSpeed';
export type GpuControlValue = number | 'auto';
export type GpuFieldMode = 'auto' | 'manual';
export type GpuCapabilityKey = 'powerLimitWatts' | 'coreClockMhz' | 'memClockMhz' | 'fanSpeedPercent';

export interface GpuSettingState {
    mode: GpuFieldMode;
    value: number | null;
}

export type GpuFieldModes = Partial<Record<GpuSettingKey, GpuFieldMode>>;
export type GpuSettingsState = Record<GpuSettingKey, GpuSettingState>;

export interface StreamRefresher {
    refresh: (resourceId: string) => Promise<JsonValue | null>;
}

export interface GpuControlConfig {
    type: GpuControlType;
    settingKey: GpuSettingKey;
    capabilityKey: GpuCapabilityKey;
    unit: string;
}

export interface GpuControlsConfigMap {
    power: GpuControlConfig;
    core: GpuControlConfig;
    memory: GpuControlConfig;
    fan: GpuControlConfig;
}

export interface GpuSliderConfigItem {
    type: GpuControlType;
    capabilityKey: GpuCapabilityKey;
    unit: string;
}

export interface GpuUiState {
    deviceId: string | null;
    saveMode: boolean;
    previewSlot: string | null;
    previewSettings: GpuSettingsState | null;
    previewSource: 'live' | 'slot';
    previewHydrated: boolean;
    applyAtBootDesired: boolean;
    bootToggleDirty: boolean;
    canStoreAppliedSettings: boolean;
    canSaveCurrentSettings: boolean;
    showSoAIBenchActions: boolean;
    soaibenchStopRequested: boolean;
    activeSlot: string | null;
    bootSlot: string | null;
    liveSettings: GpuSettingsState | null;
    slotMetadata: GpuSlotEntry | null;
    pending: boolean;
    applyCapability: ApplyCapability | null;
    initialized: boolean;
}

export interface ApplyCapability {
    canApply: boolean;
    mode: 'direct' | 'slot';
    slot: string | null;
    normalized: GpuSettingsState;
    snapshot: GpuSnapshot;
    applyAtBoot?: boolean;
}

export interface OffsetControlContext {
    defaultAbs: number;
    offsetMin: number;
    offsetMax: number;
}

export interface SliderElements {
    slider?: HTMLInputElement;
    valueLabel?: HTMLElement;
    toggle?: HTMLInputElement;
    toggleLabel?: HTMLElement;
    container?: HTMLElement;
}

export interface GpuSnapshotControl {
    mode: 'auto' | 'manual';
    value: number | null;
}

export interface GpuSnapshot {
    power: GpuSnapshotControl;
    core: GpuSnapshotControl;
    memory: GpuSnapshotControl;
    fan: GpuSnapshotControl;
}

export interface ConstructorOptions {
    security?: SecurityService;
}

export interface SecurityService {
    escapeHtml: (value: string) => string;
    escapeAttribute: (value: string) => string;
}

export interface GpuControlManagerDependencies {
    dom: { getDocument: () => Document };
    api: ApiService;
    chartOhlc: ChartOhlcNumeric;
    runPageTask: (taskId: string, taskFunctionValue: () => Promise<void>, options: TaskOptions) => Promise<void>;
    showNotification: (message: string, type: string) => void;
    showSoAIBenchHistory: (request: SoAIBenchHistoryOpenRequest) => Promise<void>;
    showSoAIBenchRun: (request: SoAIBenchRunOpenRequest) => Promise<void>;
    handleSoAIBenchRunsUpdate: (value: JsonValue | null) => void;
    resolveStreamManager: () => Promise<StreamRefresher>;
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
}

export interface ApiService {
    hardware: {
        gpuSettings: {
            updateDevice: (deviceId: string, payload: GpuSettingsUpdatePayload) => Promise<GpuOperationResponse>;
        };
        gpuSoAIBench: {
            start: (deviceId: string, payload: GpuSoAIBenchStartPayload) => Promise<GpuOperationResponse>;
            stop: (runId: string) => Promise<GpuOperationResponse>;
            runs: (payload: GpuSoAIBenchRunLookupPayload) => Promise<GpuOperationResponse>;
        };
        gpuSlots: {
            apply: (deviceId: string, slot: string, boot: boolean | undefined) => Promise<GpuOperationResponse>;
            store: (deviceId: string, slot: string, payload: GpuSlotStorePayload) => Promise<GpuOperationResponse>;
        };
    };
}

export type GpuSettingsUpdatePayload = Partial<Record<GpuSettingKey, number | 'auto'>> & {
    resetClocks?: boolean;
};

export interface GpuSlotStorePayload {
    settings: GpuSettingsUpdatePayload;
    fieldModes: GpuFieldModes;
}

export interface ChartOhlcNumeric {
    resolveNumeric: (...values: (JsonValue | null)[]) => number | null;
}

export interface TaskOptions {
    displayName: string;
    telemetryContext: JsonObject;
    telemetryTags: string[];
    throwOnError: boolean;
    notifyOnError: boolean;
}

export type GpuSlotEntry = GpuSlotDevice;
export type GpuSlotsByIndex = Record<string, GpuSlotDevice>;

export interface GpuSavedSettingsState {
    byIndex?: GpuSlotsByIndex;
}
