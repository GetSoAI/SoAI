/* SoAI - Hardware feature start result [frontend/assets/ts/features/hardware/modals/soaibenchrun/startResult.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { GpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import { presentGpuSoAIBenchRun } from '@features/hardware/modals/soaibenchrun/mappers.ts';
import type { SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';

interface SoAIBenchRunStartResult {
    run: SoAIBenchRunRecord | null;
    acceptedRunId: string | null;
    failureReason: string | null;
}

const startFailureReason = (result: GpuOperationResponse): string => {
    if (result.unsupportedReason?.trim()) {
        return result.unsupportedReason.trim();
    }
    if (result.failureReason?.trim()) {
        return result.failureReason.trim();
    }
    return result.status?.trim() || i18n.t('hardware.modals.soaibenchRun.progress.startFailed');
};

const resolveSoAIBenchRunStartResult = (result: GpuOperationResponse): SoAIBenchRunStartResult => {
    const run = presentGpuSoAIBenchRun(result);
    if (run) {
        return { run, acceptedRunId: null, failureReason: null };
    }
    const accepted = result.accepted === true;
    const runId = result.runId?.trim() ?? '';
    if (accepted && runId) {
        return { run: null, acceptedRunId: runId, failureReason: null };
    }
    return { run: null, acceptedRunId: null, failureReason: startFailureReason(result) };
};

export { resolveSoAIBenchRunStartResult };
export type { SoAIBenchRunStartResult };
