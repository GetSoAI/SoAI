/* SoAI - SoAI Bench background start, stop, and status settlement [frontend/assets/ts/features/hardware/modals/soaibenchrun/runSettlement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSoAIBenchStartRequest } from '@core/api/contracts/hardwareContractTypes.ts';
import { decodeGpuOperationResponse, type GpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import { serializeGpuRunIdentifierRequest, serializeGpuSoAIBenchDeviceStartRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import { ensureError, extractUserFacingErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { SnapshotError } from '@core/websocketclient/snapshotManager.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { findActiveRunForDevice, normalizeRunRecord } from '@features/hardware/modals/soaibenchrun/mappers.ts';
import { resolveSoAIBenchRunStartResult } from '@features/hardware/modals/soaibenchrun/startResult.ts';
import type { SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';

type SoAIBenchStartOutcome = { type: 'abandoned' } | { type: 'attached' } | { type: 'conflict' } | { type: 'accepted'; runId: string } | { type: 'rejected'; reason: string; error: Error | null } | { type: 'unconfirmed'; error: Error } | { type: 'unresolved'; error: Error };

interface SoAIBenchStartSettlementHost {
    refreshRuns(): Promise<JsonObject>;
    isVisitActive(): boolean;
    boundRunId(): string | null;
}

const CERTIFIED_START_REQUEST: GpuSoAIBenchStartRequest = { profile: 'standard', benchmarkMode: 'certified' };

const recoverLostStart = async (host: SoAIBenchStartSettlementHost, error: Error): Promise<SoAIBenchStartOutcome> => {
    try {
        await host.refreshRuns();
    } catch {
        return host.isVisitActive() ? { type: 'unresolved', error } : { type: 'abandoned' };
    }
    if (!host.isVisitActive()) {
        return { type: 'abandoned' };
    }
    return host.boundRunId() === null ? { type: 'unconfirmed', error } : { type: 'attached' };
};

const resolveStartResponse = (response: GpuOperationResponse): SoAIBenchStartOutcome => {
    const result = resolveSoAIBenchRunStartResult(response);
    return result.acceptedRunId === null ? { type: 'rejected', reason: result.failureReason, error: null } : { type: 'accepted', runId: result.acceptedRunId };
};

const settleSoAIBenchStart = async (host: SoAIBenchStartSettlementHost, deviceId: string): Promise<SoAIBenchStartOutcome> => {
    const payload = await host.refreshRuns();
    if (!host.isVisitActive()) {
        return { type: 'abandoned' };
    }
    if (host.boundRunId() !== null) {
        return { type: 'attached' };
    }
    if (findActiveRunForDevice(payload, deviceId) !== null) {
        return { type: 'conflict' };
    }
    let response: GpuOperationResponse;
    try {
        response = decodeGpuOperationResponse(await requestWebSocketSnapshotRecord('hardware.gpu.soaibench.start', serializeGpuSoAIBenchDeviceStartRequest(deviceId, CERTIFIED_START_REQUEST)));
    } catch (error) {
        const runtimeError = ensureError(error);
        if (runtimeError instanceof SnapshotError) {
            return { type: 'rejected', reason: extractUserFacingErrorMessage(runtimeError) ?? i18n.t('hardware.modals.soaibenchRun.progress.startFailed'), error: runtimeError };
        }
        return recoverLostStart(host, runtimeError);
    }
    return resolveStartResponse(response);
};

const requestRunRecord = async (resourceName: string, runId: string): Promise<SoAIBenchRunRecord> => {
    const run = normalizeRunRecord(await requestWebSocketSnapshotRecord(resourceName, serializeGpuRunIdentifierRequest(runId)));
    if (run === null || run.runId !== runId) {
        throw new TypeError(`${resourceName} response did not identify the requested run`);
    }
    return run;
};

const requestSoAIBenchStop = (runId: string): Promise<SoAIBenchRunRecord> => requestRunRecord('hardware.gpu.soaibench.stop', runId);

const lookupSoAIBenchRunStatus = (runId: string): Promise<SoAIBenchRunRecord> => requestRunRecord('hardware.gpu.soaibench.status', runId);

export { lookupSoAIBenchRunStatus, requestSoAIBenchStop, settleSoAIBenchStart };
export type { SoAIBenchStartOutcome, SoAIBenchStartSettlementHost };
