/* SoAI - Hardware page initial snapshots controller [frontend/assets/ts/pages/hardware/controllers/realtime/initialSnapshotsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { ensureError, extractErrorCode } from '@core/errors/coerce.ts';
import { SnapshotError } from '@core/websocketclient/snapshotManager.ts';
import type { HardwareGpuResource } from '@pages/hardware/controllers/realtime/gpuResourceState.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS, HARDWARE_PROCESSES } from '@core/realtime/streammanager/resources/ids.ts';
import { requestWebSocketSnapshotArray, requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { normalizeGpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesResource.ts';
import { decodeGpuSlotsSnapshot } from '@core/realtime/streammanager/resources/gpuSlotsResource.ts';
import { decodeHardwareProcessesResource } from '@core/realtime/streammanager/resources/resourceDecoders.ts';

interface HardwareInitialSnapshotHost {
    hasGrantedAction(action: string): boolean;
    hasProcessPanel(): boolean;
    gpuResourceAvailable(resource: HardwareGpuResource): boolean;
    gpuResourceGeneration(resource: HardwareGpuResource): number;
    handleGpuResourceUnavailable(resource: HardwareGpuResource, error: Error): void;
    handleGpuCapabilities(value: JsonValue): void;
    handleProcessResourceUpdate(value: JsonValue): void;
    handleSavedGpuSettings(value: JsonValue): void;
}

const loadHardwareInitialRealtimeSnapshots = async (host: HardwareInitialSnapshotHost, signal?: AbortSignal): Promise<void> => {
    throwIfAborted(signal);
    if (host.hasProcessPanel() && host.hasGrantedAction('HW_PROCESS_VIEW')) {
        const processes = decodeHardwareProcessesResource(await requestWebSocketSnapshotArray(HARDWARE_PROCESSES, null, { signal }));
        throwIfAborted(signal);
        if (host.hasGrantedAction('HW_PROCESS_VIEW')) host.handleProcessResourceUpdate(processes);
    }
    if (!host.hasGrantedAction('HW_GPU_TUNING')) return;
    const capabilitiesGeneration = host.gpuResourceGeneration('capabilities');
    const slotsGeneration = host.gpuResourceGeneration('slots');
    const [capabilities, slots] = await Promise.allSettled([host.gpuResourceAvailable('capabilities') ? Promise.resolve(null) : requestWebSocketSnapshotRecord(HARDWARE_GPU_CAPABILITIES, null, { signal }).then((value) => normalizeGpuCapabilitiesResource(value)), host.gpuResourceAvailable('slots') ? Promise.resolve(null) : requestWebSocketSnapshotRecord(HARDWARE_GPU_SLOTS, null, { signal }).then((value) => decodeGpuSlotsSnapshot(value))]);
    throwIfAborted(signal);
    if (!host.hasGrantedAction('HW_GPU_TUNING')) return;
    for (const result of [capabilities, slots]) {
        if (result.status !== 'rejected') continue;
        const error = ensureError(result.reason);
        if (error instanceof SnapshotError) {
            const errorCode = extractErrorCode(error.payload);
            if (errorCode === 'forbidden_error' || errorCode === 'authentication_error') throw error;
        }
    }
    if (host.gpuResourceGeneration('capabilities') === capabilitiesGeneration) {
        if (capabilities.status === 'fulfilled') {
            if (capabilities.value !== null) host.handleGpuCapabilities(capabilities.value);
        } else host.handleGpuResourceUnavailable('capabilities', ensureError(capabilities.reason));
    }
    if (host.gpuResourceGeneration('slots') === slotsGeneration) {
        if (slots.status === 'fulfilled') {
            if (slots.value !== null) host.handleSavedGpuSettings(slots.value);
        } else host.handleGpuResourceUnavailable('slots', ensureError(slots.reason));
    }
};

export { loadHardwareInitialRealtimeSnapshots };
