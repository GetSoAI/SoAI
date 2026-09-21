/* SoAI - Hardware benchmark closed-start settlement [frontend/assets/ts/features/hardware/modals/soaibenchrun/startSettlement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import { serializeGpuRunIdentifierRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { findActiveStandardRunForDevice, isTerminalSoAIBenchStatus } from '@features/hardware/modals/soaibenchrun/mappers.ts';
import { resolveSoAIBenchRunStartResult } from '@features/hardware/modals/soaibenchrun/startResult.ts';
import type { SoAIBenchRunModalHost, SoAIBenchRunSession } from '@features/hardware/modals/soaibenchrun/types.ts';

const stopAcceptedRunAfterClosedStart = async (host: SoAIBenchRunModalHost, session: SoAIBenchRunSession, options: { result?: GpuOperationResponse; runsPayload?: JsonObject | null } = {}): Promise<void> => {
    if (options.result) {
        const startResult = resolveSoAIBenchRunStartResult(options.result);
        if (startResult.run && !isTerminalSoAIBenchStatus(startResult.run.status)) {
            session.runId = startResult.run.runId;
        } else {
            session.runId = startResult.acceptedRunId;
        }
    }
    const runsPayload = options.runsPayload === undefined && !session.runId ? await host.refreshSoAIBenchRuns() : options.runsPayload;
    session.runId = session.runId ?? findActiveStandardRunForDevice(runsPayload ?? null, session.deviceId)?.runId ?? null;
    if (!session.runId || session.stopRequestSent) {
        return;
    }
    session.stopRequestSent = true;
    try {
        await requestWebSocketSnapshotRecord('hardware.gpu.soaibench.stop', serializeGpuRunIdentifierRequest(session.runId));
    } catch (error) {
        session.stopRequestSent = false;
        throw error;
    }
};

export { stopAcceptedRunAfterClosedStart };
