/* SoAI - Shared frontend API endpoint layer hardware [frontend/assets/ts/core/api/endpoints/hardware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeSuccessfulMutationResponse, type SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { buildSignalRequestOptions } from '@core/api/requestOptions.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { HardwareHistoryConfig, HardwareSnapshotOptions, KillProcessOptions } from '@core/api/types/hardware.ts';
import type { ApiQueryParameters, RequestOptions } from '@core/api/types/request.ts';
import { decodeGpuOperationResponse, decodeHardwareCapabilities, decodeHardwareExportResponse, decodeHardwareSnapshot, decodeKillProcessResponse, decodeOptionalHardwareHistory, type GpuOperationResponse, type GpuSettingsUpdateRequest, type GpuSlotStoreRequest, type GpuSoAIBenchStartRequest, type HardwareCapabilitiesResponse, type HardwareHistoryResponse, type HardwareSnapshotResponse, type KillProcessResponse } from '@core/api/contracts/hardwareContracts.ts';
import { serializeGpuDeviceRequest, serializeGpuDeviceSettingsRequest, serializeGpuSlotApplyDeviceRequest, serializeGpuSlotBootRequest, serializeGpuSlotStoreRequest, serializeGpuSoAIBenchDeviceStartRequest, serializeKillProcessRestRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import { decodeGpuSoAIBenchPublicationReceipt, decodeGpuSoAIBenchPublicationPreview } from '@core/api/contracts/hardwareSoAIBenchPublicationContracts.ts';
import type { GpuSoAIBenchPublicationReceipt } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
import { toLowerCase, toString, toTrimmedString } from '@core/normalize.ts';
import { isDefined, isFiniteNumber, isNumber } from '@core/typeGuards.ts';
import { minutesToMs } from '@core/time/durations.ts';
import { serverEpochMs } from '@core/time/clock.ts';

const createHardwareEndpoints = (
    api: ApiClientContext
): {
    capabilities: (options?: RequestOptions) => Promise<HardwareCapabilitiesResponse>;
    snapshot: (options?: HardwareSnapshotOptions) => Promise<HardwareSnapshotResponse>;
    gpuSettings: { updateDevice: (deviceId: string, settings: GpuSettingsUpdateRequest) => Promise<GpuOperationResponse> };
    gpuSoAIBench: { deleteLocal: (runId: string) => Promise<SuccessfulMutationResponse>; preview: (runId: string) => Promise<string>; start: (deviceId: string, payload: GpuSoAIBenchStartRequest) => Promise<GpuOperationResponse>; get: (runId: string) => Promise<GpuOperationResponse>; stop: (runId: string) => Promise<GpuOperationResponse>; publish: (runId: string) => Promise<GpuSoAIBenchPublicationReceipt>; history: (deviceId: string, limit: number) => Promise<GpuOperationResponse>; exportHistory: (deviceId: string) => Promise<Response> };
    gpuSlots: { store: (deviceId: string, slot: string | number, slotPayload: GpuSlotStoreRequest, applyAtBoot?: boolean | undefined) => Promise<GpuOperationResponse>; preview: (deviceId: string, slot: string | number) => Promise<GpuOperationResponse>; apply: (deviceId: string, slot: string | number, applyAtBoot?: boolean | undefined) => Promise<GpuOperationResponse>; toggleBoot: (deviceId: string, slot: string | number, enabled: boolean) => Promise<GpuOperationResponse>; clear: (deviceId: string, slot: string | number) => Promise<GpuOperationResponse> };
    killProcess: (pid: string | number, options?: number | KillProcessOptions) => Promise<KillProcessResponse>;
    history: (config: HardwareHistoryConfig) => Promise<HardwareHistoryResponse | null>;
} => {
    return {
        capabilities: async (options: RequestOptions = {}): Promise<HardwareCapabilitiesResponse> => decodeHardwareCapabilities(await api.get('/api/v1/hardware/capabilities', options)),
        snapshot: async (options: HardwareSnapshotOptions = {}): Promise<HardwareSnapshotResponse> => {
            const query: ApiQueryParameters = {};
            if (options.components && options.components.length > 0) {
                query['components'] = options.components.join(',');
            }
            if (isDefined(options.useCache)) {
                query['cache'] = options.useCache;
            }
            return decodeHardwareSnapshot(
                await api.get('/api/v1/hardware/snapshot', {
                    ...buildSignalRequestOptions(options),
                    query
                })
            );
        },
        gpuSettings: { updateDevice: async (deviceId: string, settings: GpuSettingsUpdateRequest): Promise<GpuOperationResponse> => decodeGpuOperationResponse(await api.post('/api/v1/hardware/gpu/settings', serializeGpuDeviceSettingsRequest(deviceId, settings))) },
        gpuSoAIBench: {
            deleteLocal: async (runId: string): Promise<SuccessfulMutationResponse> => decodeSuccessfulMutationResponse(await api.delete(`/api/v1/hardware/gpu/soaibench/runs/${api.encodePathSegment(runId)}`), 'SoAIBench local history deletion'),
            preview: async (runId: string): Promise<string> => {
                if (!runId) throw new Error('SoAIBench runId is required');
                return decodeGpuSoAIBenchPublicationPreview(await api.get(`/api/v1/hardware/gpu/soaibench/runs/${api.encodePathSegment(runId)}/publication/preview`));
            },
            start: async (deviceId: string, payload: GpuSoAIBenchStartRequest): Promise<GpuOperationResponse> => {
                if (!deviceId) throw new Error('GPU deviceId is required');
                return decodeGpuOperationResponse(await api.post('/api/v1/hardware/gpu/soaibench/runs', serializeGpuSoAIBenchDeviceStartRequest(deviceId, payload)));
            },
            get: async (runId: string): Promise<GpuOperationResponse> => {
                if (!runId) throw new Error('SoAIBench runId is required');
                return decodeGpuOperationResponse(await api.get(`/api/v1/hardware/gpu/soaibench/runs/${api.encodePathSegment(runId)}`));
            },
            stop: async (runId: string): Promise<GpuOperationResponse> => {
                if (!runId) throw new Error('SoAIBench runId is required');
                return decodeGpuOperationResponse(await api.post(`/api/v1/hardware/gpu/soaibench/runs/${api.encodePathSegment(runId)}/stop`, {}));
            },
            publish: async (runId: string): Promise<GpuSoAIBenchPublicationReceipt> => {
                if (!runId) throw new Error('SoAIBench runId is required');
                return decodeGpuSoAIBenchPublicationReceipt(await api.post(`/api/v1/hardware/gpu/soaibench/runs/${api.encodePathSegment(runId)}/publication`));
            },
            history: async (deviceId: string, limit: number): Promise<GpuOperationResponse> => {
                if (!deviceId) throw new Error('GPU deviceId is required');
                return decodeGpuOperationResponse(await api.get('/api/v1/hardware/gpu/soaibench/runs', { query: { 'device_id': deviceId, limit } }));
            },
            exportHistory: async (deviceId: string): Promise<Response> => {
                if (!deviceId) throw new Error('GPU deviceId is required');
                return decodeHardwareExportResponse(await api.get('/api/v1/hardware/gpu/soaibench/history/export', { query: { 'device_id': deviceId }, rawResponse: true }));
            }
        },
        gpuSlots: {
            store: async (deviceId: string, slot: string | number, slotPayload: GpuSlotStoreRequest, applyAtBoot: boolean | undefined = undefined): Promise<GpuOperationResponse> => {
                const slotId = isNumber(slot) ? toString(slot) : toTrimmedString(slot);
                if (!slotId) throw new Error('GPU slot identifier is required');
                if (!deviceId) throw new Error('GPU deviceId is required');
                const payload = serializeGpuSlotStoreRequest(deviceId, slotPayload, applyAtBoot === undefined ? undefined : Boolean(applyAtBoot));
                return decodeGpuOperationResponse(await api.post(`/api/v1/hardware/gpu/slots/${api.encodePathSegment(slotId)}/store`, payload));
            },
            preview: async (deviceId: string, slot: string | number): Promise<GpuOperationResponse> => {
                const slotId = isNumber(slot) ? toString(slot) : toTrimmedString(slot);
                if (!slotId) throw new Error('GPU slot identifier is required');
                if (!deviceId) throw new Error('GPU deviceId is required');
                return decodeGpuOperationResponse(await api.post(`/api/v1/hardware/gpu/slots/${api.encodePathSegment(slotId)}/preview`, serializeGpuDeviceRequest(deviceId)));
            },
            apply: async (deviceId: string, slot: string | number, applyAtBoot: boolean | undefined = undefined): Promise<GpuOperationResponse> => {
                const slotId = isNumber(slot) ? toString(slot) : toTrimmedString(slot);
                if (!slotId) throw new Error('GPU slot identifier is required');
                if (!deviceId) throw new Error('GPU deviceId is required');
                const payload = serializeGpuSlotApplyDeviceRequest(deviceId, applyAtBoot === undefined ? undefined : Boolean(applyAtBoot));
                return decodeGpuOperationResponse(await api.post(`/api/v1/hardware/gpu/slots/${api.encodePathSegment(slotId)}/apply`, payload));
            },
            toggleBoot: async (deviceId: string, slot: string | number, enabled: boolean): Promise<GpuOperationResponse> => {
                const slotId = isNumber(slot) ? toString(slot) : toTrimmedString(slot);
                if (!slotId) throw new Error('GPU slot identifier is required');
                if (!deviceId) throw new Error('GPU deviceId is required');
                return decodeGpuOperationResponse(await api.patch(`/api/v1/hardware/gpu/slots/${api.encodePathSegment(slotId)}/boot`, serializeGpuSlotBootRequest(deviceId, Boolean(enabled))));
            },
            clear: async (deviceId: string, slot: string | number): Promise<GpuOperationResponse> => {
                const slotId = isNumber(slot) ? toString(slot) : toTrimmedString(slot);
                if (!slotId) throw new Error('GPU slot identifier is required');
                if (!deviceId) throw new Error('GPU deviceId is required');
                return decodeGpuOperationResponse(
                    await api.delete(`/api/v1/hardware/gpu/slots/${api.encodePathSegment(slotId)}`, {
                        body: serializeGpuDeviceRequest(deviceId)
                    })
                );
            }
        },
        killProcess: async (pid: string | number, options: number | KillProcessOptions = {}): Promise<KillProcessResponse> => {
            let signal = 15;
            let useSudo = false;
            const normalizedPid = isNumber(pid) ? toString(pid) : toTrimmedString(pid);
            if (!normalizedPid) throw new Error('Process identifier is required');
            if (isNumber(options)) signal = options;
            else {
                const normalizedOptions = options;
                const signalValue = normalizedOptions['signal'];
                if (isDefined(signalValue)) {
                    const candidate = Number(signalValue);
                    if (isFiniteNumber(candidate) && candidate > 0) signal = Math.floor(candidate);
                }
                const useSudoValue = normalizedOptions.useSudo;
                if (isDefined(useSudoValue)) useSudo = Boolean(useSudoValue);
            }
            return decodeKillProcessResponse(await api.post(`/api/v1/actions/processes/${api.encodePathSegment(normalizedPid)}/kill`, serializeKillProcessRestRequest(signal, useSudo)));
        },
        history: async (config: HardwareHistoryConfig): Promise<HardwareHistoryResponse | null> => {
            const component = toLowerCase(config.component || 'cpu');
            const parameters: ApiQueryParameters = { component };
            const identifier = toTrimmedString(config.identifier);
            if (component === 'gpu') {
                const gpuIndex = Number(config.gpuIndex);
                if (!isFiniteNumber(gpuIndex)) throw new Error('hardware.history gpuIndex is required for gpu component');
                parameters['gpu_index'] = Math.max(0, Math.floor(gpuIndex));
            }
            if ((component === 'disk' || component === 'network') && identifier) parameters['identifier'] = identifier;

            let start = Number(config.startTsMs);
            let end = Number(config.endTsMs);
            const minutes = Number(config.minutes);
            const windowMs = (): number => Math.max(minutesToMs(1), Math.round(minutesToMs(minutes)));

            if (!isFiniteNumber(start) && isFiniteNumber(end) && isFiniteNumber(minutes)) start = end - windowMs();
            else if (!isFiniteNumber(end) && isFiniteNumber(start) && isFiniteNumber(minutes)) end = start + windowMs();
            else if (!isFiniteNumber(start) && !isFiniteNumber(end) && isFiniteNumber(minutes)) {
                const now = Math.floor(serverEpochMs());
                end = now;
                start = now - windowMs();
            }
            if (isFiniteNumber(start)) parameters['start_ts_ms'] = Math.floor(start);
            if (isFiniteNumber(end)) parameters['end_ts_ms'] = Math.floor(end);
            if (isFiniteNumber(parameters['start_ts_ms']) && isFiniteNumber(parameters['end_ts_ms']) && parameters['start_ts_ms'] > parameters['end_ts_ms']) {
                [parameters['start_ts_ms'], parameters['end_ts_ms']] = [parameters['end_ts_ms'], parameters['start_ts_ms']];
            }

            const points = Number(config.points);
            if (isFiniteNumber(points) && points > 0) parameters['points'] = Math.max(1, Math.floor(points));
            const intervalMs = Number(config.intervalMs);
            if (isFiniteNumber(intervalMs) && intervalMs > 0) parameters['interval_ms'] = Math.max(1, Math.floor(intervalMs));
            if (config.aggregation) parameters['aggregation'] = toLowerCase(config.aggregation);

            const requestOptions = buildSignalRequestOptions(config.options ?? {});
            return decodeOptionalHardwareHistory(await api.get('/api/v1/hardware/history', { query: parameters, ...requestOptions }));
        }
    };
};

export { createHardwareEndpoints };
