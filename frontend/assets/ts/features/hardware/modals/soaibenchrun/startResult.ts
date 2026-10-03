/* SoAI - Hardware feature start result [frontend/assets/ts/features/hardware/modals/soaibenchrun/startResult.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { GpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';

type SoAIBenchRunStartResult = { acceptedRunId: string; failureReason: null } | { acceptedRunId: null; failureReason: string };

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
    const runId = result.runId?.trim() ?? '';
    if (result.accepted === true && runId) {
        return { acceptedRunId: runId, failureReason: null };
    }
    return { acceptedRunId: null, failureReason: startFailureReason(result) };
};

export { resolveSoAIBenchRunStartResult };
export type { SoAIBenchRunStartResult };
