/* SoAI - Hardware feature session state [frontend/assets/ts/features/hardware/modals/soaibenchrun/sessionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { isTerminalSoAIBenchStatus } from '@features/hardware/modals/soaibenchrun/mappers.ts';
import type { SoAIBenchRunOpenRequest, SoAIBenchRunRecord, SoAIBenchRunSession } from '@features/hardware/modals/soaibenchrun/types.ts';

class SoAIBenchRunSessionState {
    session: SoAIBenchRunSession | null = null;
    runsPayload: JsonObject | null = null;
    latestRun: SoAIBenchRunRecord | null = null;
    terminalReason: string | null = null;

    clearFinishedSession(): void {
        const session = this.session;
        if (session?.starting) {
            return;
        }
        if (!session || !session.runId || (this.latestRun && isTerminalSoAIBenchStatus(this.latestRun.status))) {
            this.session = null;
            this.latestRun = null;
            this.terminalReason = null;
        }
    }

    open(request: SoAIBenchRunOpenRequest, activeRun: SoAIBenchRunRecord | null): void {
        this.session = {
            deviceId: request.deviceId,
            gpuIndex: request.gpuIndex,
            gpuName: request.gpuName,
            runId: activeRun?.runId ?? null,
            updateSeq: activeRun?.updateSeq ?? 0,
            token: Symbol('hardware-soaibench-run-modal'),
            cancelRequested: false,
            starting: false
        };
        this.latestRun = activeRun;
        this.terminalReason = null;
    }

    requireSession(): SoAIBenchRunSession {
        const session = this.session;
        if (!session) {
            throw new Error('SoAIBench run modal requires an active session');
        }
        return session;
    }

    requireLatestRun(errorMessage: string): SoAIBenchRunRecord {
        const run = this.latestRun;
        if (!run) {
            throw new Error(errorMessage);
        }
        return run;
    }

    request(): SoAIBenchRunOpenRequest {
        const session = this.requireSession();
        return { deviceId: session.deviceId, gpuIndex: session.gpuIndex, gpuName: session.gpuName };
    }

    attachRun(run: SoAIBenchRunRecord): void {
        const session = this.requireSession();
        session.runId = run.runId;
        session.updateSeq = run.updateSeq;
        this.latestRun = run;
        this.terminalReason = null;
    }

    isCurrent(session: SoAIBenchRunSession): boolean {
        return this.session?.token === session.token;
    }

    prepareForStart(session: SoAIBenchRunSession): void {
        const latestRun = this.latestRun;
        if (latestRun && isTerminalSoAIBenchStatus(latestRun.status)) {
            session.runId = null;
            session.updateSeq = 0;
            this.latestRun = null;
        }
        this.terminalReason = null;
    }
}

export { SoAIBenchRunSessionState };
