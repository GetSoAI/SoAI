/* SoAI - SoAI Bench run phase and activity semantics [frontend/assets/ts/features/hardware/modals/soaibenchrun/runPhase.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isTerminalSoAIBenchStatus } from '@features/hardware/modals/soaibenchrun/mappers.ts';
import type { SoAIBenchActivityState, SoAIBenchRunEntry, SoAIBenchRunPhase } from '@features/hardware/modals/soaibenchrun/types.ts';

const resolveSoAIBenchRunPhase = (entry: SoAIBenchRunEntry): SoAIBenchRunPhase => {
    if (entry.run !== null && isTerminalSoAIBenchStatus(entry.run.status)) {
        return 'terminal';
    }
    if (entry.settlement === 'rejected') {
        return 'rejected';
    }
    if (entry.settlement === 'unresolved') {
        return 'unresolved';
    }
    if (entry.runId === null) {
        return 'starting';
    }
    return entry.stopPending || (entry.run !== null && entry.run.stopRequestedAtMs !== null) ? 'stopping' : 'running';
};

const resolveSoAIBenchActivityState = (phase: SoAIBenchRunPhase): SoAIBenchActivityState | null => {
    return phase === 'terminal' || phase === 'rejected' ? null : phase;
};

const isSoAIBenchRunEntryActive = (entry: SoAIBenchRunEntry): boolean => resolveSoAIBenchActivityState(resolveSoAIBenchRunPhase(entry)) !== null;

export { isSoAIBenchRunEntryActive, resolveSoAIBenchActivityState, resolveSoAIBenchRunPhase };
