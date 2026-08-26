/* SoAI - Stream protocol type declarations [frontend/assets/ts/core/types/streamTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

import type { ModelData } from '@core/types/modelTypes.ts';

export interface LogSnapshotData {
    entries: JsonObject[];
    source?: string;
    limit?: number;
}

export type { ModelData } from '@core/types/modelTypes.ts';

export interface PluginData {
    name: string;
    state?: string;
    isEnabled?: boolean;
    circuitBreaker?: JsonObject;
    providers?: JsonValue[];
}

export type GpuSlotSettings = JsonObject & { powerLimit?: number | 'auto' | null; coreClock?: number | 'auto' | null; memClock?: number | 'auto' | null; fanSpeed?: number | 'auto' | null; resetClocks?: boolean };
export type GpuSlotFieldModes = JsonObject & { powerLimit?: 'auto' | 'manual'; coreClock?: 'auto' | 'manual'; memClock?: 'auto' | 'manual'; fanSpeed?: 'auto' | 'manual' };
export type GpuSlotSavedState = JsonObject & { settings: GpuSlotSettings; fieldModes: GpuSlotFieldModes; savedAt?: string; lastAppliedAt?: string | null; signature?: string };
export type GpuSlotBootState = JsonObject & { enabled: boolean; slot: string | null; appliedSignature: string | null; appliedAt: string | null };
export type GpuSlotCurrentSetting = JsonObject & { value: number; defaultValue?: number; isDefault?: boolean };
export type GpuSlotLiveState = JsonObject & { deviceId: string; currentSettings: Record<string, GpuSlotCurrentSetting>; bootState: GpuSlotBootState; bootEnabled: boolean; bootSlot: string | null; activeSlot: string | null; activeSignature: string | null; activeAppliedAt: string | null };
export type GpuSlotDevice = JsonObject & {
    deviceId: string;
    name: string | null;
    gpuIndex: number | null;
    fieldModes?: GpuSlotFieldModes;
    appliedSettings?: GpuSlotSettings;
    slots: Record<string, GpuSlotSavedState>;
    boot: GpuSlotBootState;
    live: GpuSlotLiveState;
};

export interface GpuSlotsData {
    version?: string | null;
    byDeviceId?: Record<string, GpuSlotDevice>;
    byIndex?: Record<number, GpuSlotDevice>;
    warnings?: JsonValue;
    error?: { code?: string; message?: string } | null;
}

export interface StreamSnapshot<T extends JsonValue = JsonValue> {
    value?: T;
}

export const RESOURCE_CONNECTION_PREFIX = 'resource.connection.';

export interface StreamActionHandlers {
    onUpdate?: (data: JsonValue) => void;
    onProgress?: (data: JsonValue) => void;
    onComplete?: (data: JsonValue) => void;
    onStreamError?: (data: JsonValue) => void;
    onError?: (error: Error) => void;
}

export interface VirtualModelsEnvelope {
    virtual?: ModelData[];
}

export interface PromptsEnvelope {
    prompts?: JsonObject[];
}

export interface SystemStatusData {
    mainState: string;
}

export interface HardwareSnapshotData {
    cpus?: Array<{
        usagePercent?: number;
        temperatureCelsius?: number;
        powerDrawWatts?: number;
    }>;
    memory?: {
        usedBytes?: number;
    };
    gpu?: {
        gpus?: JsonValue[];
    };
    summary?: {
        totalVramGb?: number;
        totalSystemRamGb?: number;
    };
}

export interface BundleDefinitionConfig {
    resources: Record<string, string>;
    stateKey?: string;
    streams?: string[];
}

export interface OperationMetadata {
    id?: string;
    type?: string;
    description?: string;
    startedAt?: number;
}

export interface StreamEventPayload {
    type?: string;
    event?: string;
}

export interface ConnectionStatusEvent {
    eventType?: string;
    connected?: boolean;
}

export interface ConnectionService {
    subscribe?: (callback: (event: ConnectionStatusEvent) => void, options?: { emitCurrent?: boolean }) => () => void;
}

export interface ErrorWithName {
    name?: string;
    message?: string;
}

export interface FulfilledResult<T> {
    status: 'fulfilled';
    value: T;
}

export type GpuSlotWarning = JsonObject & { type: string; deviceIds: string[]; message: string };
export type GpuSlotsBuilderResult = JsonObject & {
    version: number | null;
    byDeviceId: Record<string, GpuSlotDevice>;
    byIndex: Record<number, GpuSlotDevice>;
    warnings: GpuSlotWarning | null;
    error: { code?: string; message?: string } | null;
};

export interface GpuSlotsUpdateContext {
    type: string;
    raw: JsonValue;
    resource: JsonValue;
    previousValue: JsonValue;
}
