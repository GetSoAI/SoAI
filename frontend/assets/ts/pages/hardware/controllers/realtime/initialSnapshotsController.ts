/* SoAI - Hardware page initial snapshots controller [frontend/assets/ts/pages/hardware/controllers/realtime/initialSnapshotsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS, HARDWARE_PROCESSES } from '@core/realtime/streammanager/resources/ids.ts';
import { requestWebSocketSnapshotArray, requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { normalizeGpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesResource.ts';
import { decodeGpuSlotsSnapshot } from '@core/realtime/streammanager/resources/gpuSlotsResource.ts';
import { decodeHardwareProcessesResource } from '@core/realtime/streammanager/resources/resourceDecoders.ts';

interface HardwareInitialSnapshotHost {
    hasGrantedAction(action: string): boolean;
    hasProcessPanel(): boolean;
    handleGpuCapabilities(value: JsonValue): void;
    handleProcessResourceUpdate(value: JsonValue): void;
    handleSavedGpuSettings(value: JsonValue): void;
}

const loadHardwareInitialRealtimeSnapshots = async (host: HardwareInitialSnapshotHost, signal?: AbortSignal): Promise<void> => {
    throwIfAborted(signal);
    if (host.hasProcessPanel() && host.hasGrantedAction('HW_PROCESS_VIEW')) {
        host.handleProcessResourceUpdate(decodeHardwareProcessesResource(await requestWebSocketSnapshotArray(HARDWARE_PROCESSES)));
        throwIfAborted(signal);
    }
    if (host.hasGrantedAction('HW_GPU_TUNING')) {
        const [capabilities, slots] = await Promise.all([requestWebSocketSnapshotRecord(HARDWARE_GPU_CAPABILITIES), requestWebSocketSnapshotRecord(HARDWARE_GPU_SLOTS)]);
        throwIfAborted(signal);
        host.handleGpuCapabilities(normalizeGpuCapabilitiesResource(capabilities));
        host.handleSavedGpuSettings(decodeGpuSlotsSnapshot(slots));
    }
};

export { loadHardwareInitialRealtimeSnapshots };
