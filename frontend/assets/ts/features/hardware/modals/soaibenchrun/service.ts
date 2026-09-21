/* SoAI - SoAI Bench run modal service [frontend/assets/ts/features/hardware/modals/soaibenchrun/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { decodeGpuOperationResponse, type GpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { serializeGpuRunIdentifierRequest, serializeGpuSoAIBenchDeviceStartRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import { HARDWARE_SOAIBENCH_RUN_MODAL_ID } from '@features/hardware/modals/constants.ts';
import { copySoAIBenchRunExport, downloadSoAIBenchRunExport } from '@features/hardware/modals/soaibenchrun/exportActions.ts';
import { exportRunFromRunRecord } from '@features/hardware/modals/soaibenchrun/exportText.ts';
import { findActiveRunForDevice, findActiveStandardRunForDevice, findRunById, isTerminalSoAIBenchStatus } from '@features/hardware/modals/soaibenchrun/mappers.ts';
import { SoAIBenchRunModalRenderer } from '@features/hardware/modals/soaibenchrun/renderer.ts';
import { SoAIBenchRunSessionState } from '@features/hardware/modals/soaibenchrun/sessionState.ts';
import { resolveSoAIBenchRunStartResult } from '@features/hardware/modals/soaibenchrun/startResult.ts';
import { stopAcceptedRunAfterClosedStart } from '@features/hardware/modals/soaibenchrun/startSettlement.ts';
import type { SoAIBenchRunModalDependencies, SoAIBenchRunModalHost, SoAIBenchRunOpenRequest, SoAIBenchRunRecord, SoAIBenchRunSession } from '@features/hardware/modals/soaibenchrun/types.ts';
import { hasSoAIBenchHistoryForDevice } from '@features/hardware/soaibenchRunsIndex.ts';
import { setRunControlsDisabled } from '@features/hardware/modals/soaibenchrun/dom.ts';

class SoAIBenchRunModal {
    readonly modalId = HARDWARE_SOAIBENCH_RUN_MODAL_ID;
    readonly host: SoAIBenchRunModalHost;
    readonly #renderer: SoAIBenchRunModalRenderer;
    readonly #state = new SoAIBenchRunSessionState();
    readonly #publishRun: SoAIBenchRunModalDependencies['publishRun'];
    #skipStopOnClose = false;

    constructor({ host, publishRun }: SoAIBenchRunModalDependencies) {
        if (!host) {
            throw new Error('SoAIBenchRunModal requires a host');
        }
        this.host = host;
        this.#publishRun = publishRun;
        this.#renderer = new SoAIBenchRunModalRenderer({
            host,
            modalId: this.modalId,
            onCancel: async () => {
                await this.#cancelActiveRun();
            }
        });
    }

    handleModalClosed(): void {
        const session = this.#state.session;
        if (!this.#skipStopOnClose && session?.starting) {
            session.stopWhenStartSettles = true;
            this.#renderer.destroyProgress();
            return;
        }
        if (!this.#skipStopOnClose && session?.runId && !session.cancelRequested && (!this.#state.latestRun || !isTerminalSoAIBenchStatus(this.#state.latestRun.status))) {
            terminateHandledPromise(this.cancelActiveRun());
            return;
        }
        const previousSession = this.#state.session;
        this.#state.clearFinishedSession();
        if (previousSession !== this.#state.session) {
            this.#renderer.destroyProgress();
        }
    }

    open(request: SoAIBenchRunOpenRequest): Promise<void> {
        return this.host.runWithBoundary('hardware:openSoAIBenchRunModal', async () => {
            const activeRun = findActiveStandardRunForDevice(this.#state.runsPayload, request.deviceId);
            this.#state.open(request, activeRun);
            if (activeRun) {
                this.#renderProgressForSession(activeRun);
            } else {
                this.#renderIntroForSession();
            }
            this.host.modals.open(this.modalId);
        });
    }

    startConfirmed(): Promise<void> {
        return this.host.runWithBoundary('hardware:startSoAIBenchRunFromModal', async () => {
            const session = this.#state.requireSession();
            if (session.starting) {
                return;
            }
            session.starting = true;
            this.#state.prepareForStart(session);
            this.#renderProgressForSession(null);
            try {
                const refreshed = await this.host.refreshSoAIBenchRuns();
                if (session.stopWhenStartSettles) {
                    await stopAcceptedRunAfterClosedStart(this.host, session, { runsPayload: refreshed });
                    this.#clearClosedStartingSession(session);
                    return;
                }
                if (!this.#isCurrentSession(session)) {
                    return;
                }
                this.handleRunsUpdate(refreshed);
                const activeRun = findActiveRunForDevice(this.#state.runsPayload, session.deviceId);
                if (activeRun) {
                    if (activeRun.profile === 'standard' && activeRun.benchmarkMode === 'certified') {
                        this.#state.attachRun(activeRun);
                        this.#renderProgressForSession(activeRun);
                    } else {
                        this.host.showNotification(i18n.t('hardware.modals.soaibenchRun.progress.activeRunInProgress'), 'warning');
                        this.#renderIntroForSession();
                    }
                    return;
                }
                const result = decodeGpuOperationResponse(await requestWebSocketSnapshotRecord('hardware.gpu.soaibench.start', serializeGpuSoAIBenchDeviceStartRequest(session.deviceId, { profile: 'standard', benchmarkMode: 'certified' })));
                if (session.stopWhenStartSettles) {
                    await stopAcceptedRunAfterClosedStart(this.host, session, { result });
                    this.#clearClosedStartingSession(session);
                    return;
                }
                if (!this.#isCurrentSession(session)) {
                    return;
                }
                this.#handleStartResult(session, result);
                await this.#refreshRunsAfterMutation(session);
            } catch (error) {
                if (session.stopWhenStartSettles) {
                    await stopAcceptedRunAfterClosedStart(this.host, session);
                    this.#clearClosedStartingSession(session);
                }
                if (this.#isCurrentSession(session) && !session.runId) {
                    this.#renderIntroForSession();
                }
                throw error;
            } finally {
                if (this.#isCurrentSession(session)) {
                    session.starting = false;
                }
            }
        });
    }

    handleFooterAction(): Promise<void> {
        const session = this.#state.requireSession();
        if (session.runId && !session.cancelRequested && (!this.#state.latestRun || !isTerminalSoAIBenchStatus(this.#state.latestRun.status))) {
            return this.cancelActiveRun();
        }
        return this.startConfirmed();
    }

    openHistory(): Promise<void> {
        return this.host.runWithBoundary('hardware:openSoAIBenchHistoryFromRunModal', async () => {
            if (!this.#hasHistoryForSession()) {
                throw new Error('SoAIBench history requires at least one run');
            }
            const request = this.#requestFromSession();
            this.#skipStopOnClose = true;
            try {
                this.host.modals.close(this.modalId, { restoreFocus: false });
            } finally {
                this.#skipStopOnClose = false;
            }
            await this.host.showSoAIBenchHistory(request);
        });
    }

    copyRun(): Promise<void> {
        return this.host.runWithBoundary('hardware:copySoAIBenchRun', async () => {
            await copySoAIBenchRunExport({
                host: this.host,
                request: this.#requestFromSession(),
                run: exportRunFromRunRecord(this.#state.requireLatestRun(i18n.t('hardware.modals.soaibenchRun.copyUnavailable')))
            });
        });
    }

    downloadRun(): Promise<void> {
        return this.host.runWithBoundary('hardware:downloadSoAIBenchRun', async () => {
            downloadSoAIBenchRunExport({
                host: this.host,
                request: this.#requestFromSession(),
                run: exportRunFromRunRecord(this.#state.requireLatestRun(i18n.t('hardware.modals.soaibenchRun.copyUnavailable')))
            });
        });
    }

    publishRun(): Promise<void> {
        return this.host.runWithBoundary('hardware:publishSoAIBenchRun', async () => {
            const run = this.#state.requireLatestRun(i18n.t('hardware.soaibenchPublication.unavailable'));
            const modalRoot = this.host.modals.requireElement(this.modalId);
            await this.#publishRun(run, (disabled) => setRunControlsDisabled(this.host, modalRoot, disabled));
        });
    }

    cancelActiveRun(): Promise<void> {
        return this.#cancelActiveRun();
    }

    #cancelActiveRun(): Promise<void> {
        return this.host.runWithBoundary('hardware:cancelSoAIBenchRunFromModal', async () => {
            const session = this.#state.requireSession();
            const runId = session.runId;
            if (!runId || session.cancelRequested) {
                return;
            }
            session.cancelRequested = true;
            this.#renderProgressForSession(this.#state.latestRun);
            try {
                await requestWebSocketSnapshotRecord('hardware.gpu.soaibench.stop', serializeGpuRunIdentifierRequest(runId));
            } catch (error) {
                if (this.#isCurrentSession(session)) {
                    session.cancelRequested = false;
                    this.#renderProgressForSession(this.#state.latestRun);
                }
                throw error;
            }
            await this.#refreshRunsAfterMutation(session);
        });
    }

    handleRunsUpdate(value: JsonObject | null): void {
        if (!isJsonObject(value)) {
            throw new TypeError('SoAIBench runs payload must be an object');
        }
        this.#state.runsPayload = value;
        const session = this.#state.session;
        if (!session) {
            return;
        }
        const nextRun = session.runId ? findRunById(value, session.runId) : findActiveStandardRunForDevice(value, session.deviceId);
        if (!nextRun) {
            return;
        }
        if (session.runId && this.#state.latestRun && nextRun.updateSeq <= session.updateSeq) {
            return;
        }
        this.#state.attachRun(nextRun);
        if (session.stopWhenStartSettles) {
            if (!isTerminalSoAIBenchStatus(nextRun.status)) {
                terminateHandledPromise(stopAcceptedRunAfterClosedStart(this.host, session));
            }
            return;
        }
        this.#renderer.setHistoryAvailable(this.#hasHistoryForSession());
        if (isTerminalSoAIBenchStatus(nextRun.status)) {
            session.cancelRequested = false;
            this.#renderReportForSession(nextRun);
            this.host.renderGpuControls({ only: [session.gpuIndex] });
            return;
        }
        this.#renderProgressForSession(nextRun);
    }

    #handleStartResult(session: SoAIBenchRunSession, result: GpuOperationResponse): void {
        const startResult = resolveSoAIBenchRunStartResult(result);
        const run = startResult.run;
        if (run) {
            this.#state.attachRun(run);
            if (isTerminalSoAIBenchStatus(run.status)) {
                this.#renderReportForSession(run);
                return;
            }
            this.#renderProgressForSession(run);
            return;
        }
        if (startResult.acceptedRunId) {
            session.runId = startResult.acceptedRunId;
            this.#renderProgressForSession(null);
            return;
        }
        const reason = startResult.failureReason;
        if (!reason) {
            throw new Error('SoAIBench rejected start without a failure reason');
        }
        this.#state.terminalReason = reason;
        this.host.showNotification(reason, 'warning');
        this.#renderReportForSession(null);
    }

    async #refreshRunsAfterMutation(session: SoAIBenchRunSession): Promise<void> {
        const refreshed = await this.host.refreshSoAIBenchRuns();
        if (!this.#state.isCurrent(session)) {
            return;
        }
        this.handleRunsUpdate(refreshed);
    }

    #clearClosedStartingSession(session: SoAIBenchRunSession): void {
        session.starting = false;
        if (this.#isCurrentSession(session)) {
            this.#state.session = null;
            this.#state.latestRun = null;
            this.#state.terminalReason = null;
        }
    }

    #isCurrentSession(session: SoAIBenchRunSession): boolean {
        return this.#state.isCurrent(session);
    }

    #requestFromSession(): SoAIBenchRunOpenRequest {
        return this.#state.request();
    }

    #hasHistoryForSession(): boolean {
        return hasSoAIBenchHistoryForDevice(this.#state.runsPayload, this.#state.requireSession().deviceId);
    }

    #renderIntroForSession(): void {
        this.#renderer.renderIntro(this.#requestFromSession(), this.#hasHistoryForSession());
    }

    #renderProgressForSession(run: SoAIBenchRunRecord | null): void {
        const session = this.#state.requireSession();
        this.#renderer.renderProgress({
            request: this.#requestFromSession(),
            run,
            cancelRequested: session.cancelRequested,
            terminalReason: null,
            runId: session.runId,
            historyAvailable: this.#hasHistoryForSession()
        });
    }

    #renderReportForSession(run: SoAIBenchRunRecord | null): void {
        this.#renderer.renderReport({
            request: this.#requestFromSession(),
            run,
            cancelRequested: false,
            terminalReason: this.#state.terminalReason,
            runId: run?.runId ?? null,
            historyAvailable: this.#hasHistoryForSession()
        });
    }
}

export { SoAIBenchRunModal };
