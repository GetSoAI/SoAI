/* SoAI - Shared realtime GPU slots resource [frontend/assets/ts/core/realtime/streammanager/resources/gpuSlotsResource.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractErrorMessage } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { decodeBoot, decodeGpuSlotDevice, decodeLive, decodeSlots } from '@core/realtime/streammanager/resources/gpuSlotContracts.ts';
import type { ResourceConfig } from '@core/realtime/streammanager/types.ts';
import { hasOwn, isArray, isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { GpuSlotDevice, GpuSlotsBuilderResult } from '@core/types/streamTypes.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface CreateGpuSlotsResourceOptions {
    fetch: (options?: { signal?: AbortSignal | undefined }) => Promise<JsonValue | null>;
}

type GpuSlotsBuilderResultCandidate = Partial<GpuSlotsBuilderResult>;

const EMPTY_GPU_SLOTS_RESULT: GpuSlotsBuilderResult = {
    version: null,
    byDeviceId: {},
    byIndex: {},
    warnings: null,
    error: null
};

const isGpuSlotsBuilderResult = (value: GpuSlotsBuilderResultCandidate | JsonValue | null | undefined): value is GpuSlotsBuilderResult => {
    if (!isObject(value)) return false;
    return hasOwn(value, 'byDeviceId') && hasOwn(value, 'byIndex') && hasOwn(value, 'version');
};

const buildGpuSlotsResult = (previousValue: GpuSlotsBuilderResult, update: Partial<GpuSlotsBuilderResult>): GpuSlotsBuilderResult => {
    const byDeviceId = update.byDeviceId ?? previousValue.byDeviceId;
    const byIndex = Object.values(byDeviceId).reduce((accumulator: Record<number, GpuSlotDevice>, device: GpuSlotDevice) => {
        if (device.gpuIndex != null) accumulator[device.gpuIndex] = device;
        return accumulator;
    }, {});
    return {
        version: update.version ?? previousValue.version,
        byDeviceId,
        byIndex,
        warnings: update.warnings ?? previousValue.warnings,
        error: hasOwn(update, 'error') ? (update.error ?? null) : previousValue.error
    };
};

const decodeGpuSlotsSnapshot = (payload: JsonValue | null, previousValue: GpuSlotsBuilderResult = EMPTY_GPU_SLOTS_RESULT): GpuSlotsBuilderResult => {
    if (!isJsonObject(payload)) throw new TypeError('GPU slots snapshot must be an object');
    if (payload['success'] === false) {
        const errorInfo: { code?: string; message?: string } = {};
        if (payload['code'] != null) errorInfo.code = String(payload['code']);
        const message = extractErrorMessage(payload['error'] ?? payload['message'] ?? payload['error_message'] ?? payload['detail']);
        if (message) errorInfo.message = message;
        return buildGpuSlotsResult(previousValue, { byDeviceId: {}, error: errorInfo });
    }
    const devicesRecord = isJsonObject(payload['devices']) ? payload['devices'] : null;
    if (devicesRecord === null) throw new TypeError('GPU slots snapshot.devices must be an object');
    const devices: Record<string, GpuSlotDevice> = {};
    for (const [deviceId, entry] of Object.entries(devicesRecord)) {
        devices[deviceId] = decodeGpuSlotDevice(deviceId, entry, `GPU slots snapshot.devices.${deviceId}`);
    }
    if (payload['version'] !== 1) throw new TypeError('GPU slots snapshot.version must be V1');
    return buildGpuSlotsResult(previousValue, { version: 1, byDeviceId: devices, error: null });
};

const createGpuSlotsResource = (options: CreateGpuSlotsResourceOptions): Partial<ResourceConfig<GpuSlotsBuilderResult>> => {
    if (!isObject(options) || !isFunction(options.fetch)) {
        throw new Error('createGpuSlotsResource requires options.fetch()');
    }

    return {
        fetch: options.fetch,
        transform: (value) => {
            if (!isGpuSlotsBuilderResult(value)) throw new TypeError('GPU slots resource must contain decoded slot state');
            return value;
        },
        normalize: (payload, context) => {
            const previousValue = context?.previousValue;
            const prev = isObject(previousValue) && isGpuSlotsBuilderResult(previousValue) ? previousValue : EMPTY_GPU_SLOTS_RESULT;
            const updateType = toTrimmedString(context?.type);
            const record = isJsonObject(payload) ? payload : null;
            const isWebsocketUpdate = Boolean(updateType && updateType.startsWith('websocket'));
            const isSnapshotUpdate = updateType === 'fetch' || Boolean(isWebsocketUpdate && record && hasOwn(record, 'devices'));

            if (isSnapshotUpdate) {
                return decodeGpuSlotsSnapshot(record, prev);
            }

            if (!isWebsocketUpdate) return prev;
            const evt = isJsonObject(payload) ? payload : null;
            if (!evt) throw new TypeError('GPU slots realtime update must be an object');
            const deviceIds = isArray(evt['device_ids']) ? evt['device_ids'].filter(isString) : [];
            const nextWarnings =
                deviceIds.length > 0 && isString(evt['message']) && evt['message']
                    ? {
                          type: toTrimmedString(evt['type']) || 'gpu_startup_warning',
                          deviceIds: deviceIds,
                          message: evt['message']
                      }
                    : prev.warnings;
            const deviceId = toTrimmedString(evt['device_id']);
            if (!deviceId) {
                if (nextWarnings !== prev.warnings) return buildGpuSlotsResult(prev, { warnings: nextWarnings });
                return prev;
            }
            const previousDevice = prev.byDeviceId[deviceId];
            if (!previousDevice) {
                if (nextWarnings !== prev.warnings) return buildGpuSlotsResult(prev, { warnings: nextWarnings });
                return prev;
            }
            const existing: GpuSlotDevice = previousDevice;
            const nextDevice: GpuSlotDevice = {
                ...existing,
                slots: hasOwn(evt, 'slots') ? decodeSlots(evt['slots'], 'GPU slots realtime update.slots') : existing.slots,
                boot: hasOwn(evt, 'boot') ? decodeBoot(evt['boot'], 'GPU slots realtime update.boot') : existing.boot,
                live: hasOwn(evt, 'live') ? decodeLive(evt['live'], 'GPU slots realtime update.live') : existing.live
            };

            if (hasOwn(evt, 'slot') || hasOwn(evt, 'signature') || hasOwn(evt, 'applied_at')) {
                const optionalText = (key: string): string | null => {
                    const value = evt[key];
                    if (value === null || value === undefined) return null;
                    if (!isString(value) || !value.trim()) throw new TypeError(`GPU slots realtime update.${key} must be a non-empty string or null`);
                    return value.trim();
                };
                nextDevice.live = { ...nextDevice.live, activeSlot: hasOwn(evt, 'slot') ? optionalText('slot') : nextDevice.live.activeSlot, activeSignature: hasOwn(evt, 'signature') ? optionalText('signature') : nextDevice.live.activeSignature, activeAppliedAt: hasOwn(evt, 'applied_at') ? optionalText('applied_at') : nextDevice.live.activeAppliedAt };
            }

            return buildGpuSlotsResult(prev, { byDeviceId: { ...prev.byDeviceId, [deviceId]: nextDevice }, warnings: nextWarnings, error: null });
        }
    };
};

export { createGpuSlotsResource, decodeGpuSlotsSnapshot, isGpuSlotsBuilderResult };
