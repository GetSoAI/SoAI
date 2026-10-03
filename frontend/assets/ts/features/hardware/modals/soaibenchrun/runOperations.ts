/* SoAI - SoAI Bench background run operations independent of modal visibility [frontend/assets/ts/features/hardware/modals/soaibenchrun/runOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { resolveSoAIBenchRunPhase } from '@features/hardware/modals/soaibenchrun/runPhase.ts';
import { lookupSoAIBenchRunStatus, requestSoAIBenchStop, settleSoAIBenchStart, type SoAIBenchStartOutcome } from '@features/hardware/modals/soaibenchrun/runSettlement.ts';
import type { SoAIBenchRunSessionState } from '@features/hardware/modals/soaibenchrun/sessionState.ts';
import type { SoAIBenchRunEntry, SoAIBenchRunModalHost, SoAIBenchRunOpenRequest, SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';

interface SoAIBenchRunOperationsDependencies {
    host: SoAIBenchRunModalHost;
    state: SoAIBenchRunSessionState;
    onChange(): void;
}

interface SoAIBenchStartedRun {
    entry: SoAIBenchRunEntry;
    settled: Promise<void>;
}

class SoAIBenchRunOperations {
    readonly #host: SoAIBenchRunModalHost;
    readonly #state: SoAIBenchRunSessionState;
    readonly #onChange: () => void;

    constructor(dependencies: SoAIBenchRunOperationsDependencies) {
        this.#host = dependencies.host;
        this.#state = dependencies.state;
        this.#onChange = dependencies.onChange;
    }

    reconcile(payload: JsonObject): void {
        const reconciliation = this.#state.reconcile(payload);
        for (const entry of reconciliation.missing) {
            terminateHandledPromise(this.#host.runWithBoundary('hardware:recoverSoAIBenchRun', () => this.#lookupStatus(entry, this.#state.visit)));
        }
        this.#onChange();
    }

    async refreshRuns(visit: number): Promise<JsonObject> {
        const payload = await this.#host.refreshSoAIBenchRuns();
        if (payload === null) {
            throw new TypeError('SoAIBench runs payload must be an object');
        }
        if (this.#state.isVisitActive(visit)) {
            this.reconcile(payload);
        }
        return payload;
    }

    start(request: SoAIBenchRunOpenRequest, reuse: SoAIBenchRunEntry | null): SoAIBenchStartedRun | null {
        const entry = this.#state.beginStart(request, reuse);
        if (entry === null) {
            return null;
        }
        const visit = this.#state.visit;
        this.#onChange();
        return { entry, settled: this.#host.runWithBoundary('hardware:startSoAIBenchRun', () => this.#settleStart(entry, visit)) };
    }

    stop(runId: string): Promise<void> {
        return this.#host.runWithBoundary('hardware:stopSoAIBenchRun', async () => {
            const entry = this.#state.requireRunEntry(runId);
            if (!this.#state.requestStop(entry)) {
                return;
            }
            const visit = this.#state.visit;
            this.#onChange();
            let run: SoAIBenchRunRecord;
            try {
                run = await requestSoAIBenchStop(runId);
            } catch (error) {
                if (this.#state.isVisitActive(visit)) {
                    this.#state.releaseStop(entry);
                    this.#onChange();
                }
                throw error;
            }
            if (!this.#state.isVisitActive(visit)) {
                return;
            }
            this.#state.applyRun(run);
            this.#onChange();
            await this.refreshRuns(visit);
        });
    }

    recover(sectionId: string): Promise<void> {
        return this.#host.runWithBoundary('hardware:recoverSoAIBenchRun', async () => {
            const entry = this.#state.requireEntry(sectionId);
            if (entry.recovering || resolveSoAIBenchRunPhase(entry) !== 'unresolved') {
                return;
            }
            const visit = this.#state.visit;
            await (entry.runId === null ? this.#recoverUnboundStart(entry, visit) : this.#lookupStatus(entry, visit));
        });
    }

    async #settleStart(entry: SoAIBenchRunEntry, visit: number): Promise<void> {
        let outcome: SoAIBenchStartOutcome;
        try {
            outcome = await settleSoAIBenchStart({ refreshRuns: () => this.refreshRuns(visit), isVisitActive: () => this.#state.isVisitActive(visit), boundRunId: () => entry.runId }, entry.request.deviceId);
        } catch (error) {
            if (!this.#state.isVisitActive(visit)) {
                return;
            }
            const runtimeError = ensureError(error);
            this.#completeStart(entry, visit, { type: 'rejected', reason: i18n.t('hardware.modals.soaibenchRun.progress.startFailed'), error: runtimeError });
            throw runtimeError;
        }
        this.#completeStart(entry, visit, outcome);
        if (outcome.type === 'unconfirmed' || outcome.type === 'unresolved' || (outcome.type === 'rejected' && outcome.error !== null)) {
            throw outcome.error;
        }
        if (outcome.type === 'accepted' && this.#state.isVisitActive(visit)) {
            await this.refreshRuns(visit);
        }
    }

    #completeStart(entry: SoAIBenchRunEntry, visit: number, outcome: SoAIBenchStartOutcome): void {
        if (!this.#state.isVisitActive(visit)) {
            return;
        }
        this.#state.finishStart(entry);
        if (outcome.type === 'accepted') {
            this.#state.bindRun(entry, outcome.runId);
        } else if (outcome.type === 'conflict') {
            this.#rejectUnbound(entry, i18n.t('hardware.modals.soaibenchRun.progress.activeRunInProgress'), 'warning');
        } else if (outcome.type === 'rejected') {
            this.#rejectUnbound(entry, outcome.reason, outcome.error === null ? 'warning' : null);
        } else if (outcome.type === 'unconfirmed') {
            this.#rejectUnbound(entry, i18n.t('hardware.modals.soaibenchRun.progress.startUnconfirmed'), null);
        } else if (outcome.type === 'unresolved' && entry.runId === null) {
            this.#state.markUnresolved(entry, i18n.t('hardware.modals.soaibenchRun.progress.statusUnavailable'));
        }
        this.#onChange();
    }

    #rejectUnbound(entry: SoAIBenchRunEntry, reason: string, notification: NotificationType | null): void {
        if (entry.runId !== null) {
            return;
        }
        this.#state.reject(entry, reason);
        if (notification !== null) {
            this.#host.showNotification(reason, notification);
        }
    }

    async #recoverUnboundStart(entry: SoAIBenchRunEntry, visit: number): Promise<void> {
        this.#state.beginRecovery(entry);
        this.#onChange();
        try {
            await this.refreshRuns(visit);
        } catch (error) {
            if (this.#state.isVisitActive(visit)) {
                this.#state.markUnresolved(entry, i18n.t('hardware.modals.soaibenchRun.progress.statusUnavailable'));
                this.#onChange();
            }
            throw error;
        }
        if (this.#state.isVisitActive(visit) && entry.runId === null) {
            this.#state.reject(entry, i18n.t('hardware.modals.soaibenchRun.progress.startUnconfirmed'));
            this.#onChange();
        }
    }

    async #lookupStatus(entry: SoAIBenchRunEntry, visit: number): Promise<void> {
        const runId = entry.runId;
        if (runId === null) {
            return;
        }
        this.#state.beginRecovery(entry);
        this.#onChange();
        let run: SoAIBenchRunRecord;
        try {
            run = await lookupSoAIBenchRunStatus(runId);
        } catch (error) {
            if (this.#state.isVisitActive(visit) && entry.runId === runId) {
                this.#state.markUnresolved(entry, i18n.t('hardware.modals.soaibenchRun.progress.statusUnavailable'));
                this.#onChange();
            }
            throw error;
        }
        if (!this.#state.isVisitActive(visit) || entry.runId !== runId) {
            return;
        }
        this.#state.completeRecovery(entry, run);
        this.#onChange();
    }
}

export { SoAIBenchRunOperations };
