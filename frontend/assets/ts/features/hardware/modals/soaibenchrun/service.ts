/* SoAI - SoAI Bench combined run modal service [frontend/assets/ts/features/hardware/modals/soaibenchrun/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DomObserver } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { HARDWARE_SOAIBENCH_RUN_MODAL_ID } from '@features/hardware/modals/constants.ts';
import { findActiveRunForDevice } from '@features/hardware/modals/soaibenchrun/mappers.ts';
import { SoAIBenchRunModalRenderer } from '@features/hardware/modals/soaibenchrun/renderer.ts';
import { SoAIBenchResultActions, type SoAIBenchResultTarget } from '@features/hardware/modals/soaibenchrun/resultActions.ts';
import { resolveSoAIBenchRunPhase } from '@features/hardware/modals/soaibenchrun/runPhase.ts';
import { SoAIBenchRunOperations } from '@features/hardware/modals/soaibenchrun/runOperations.ts';
import { SoAIBenchGpuSelection } from '@features/hardware/modals/soaibenchrun/selection.ts';
import { SoAIBenchRunSessionState } from '@features/hardware/modals/soaibenchrun/sessionState.ts';
import type { SoAIBenchActivityProjection, SoAIBenchActivityState, SoAIBenchRunModalDependencies, SoAIBenchRunModalHost, SoAIBenchRunOpenRequest, SoAIBenchRunsFreshness } from '@features/hardware/modals/soaibenchrun/types.ts';

class SoAIBenchRunModal implements SoAIBenchActivityProjection {
    readonly modalId = HARDWARE_SOAIBENCH_RUN_MODAL_ID;
    readonly host: SoAIBenchRunModalHost;
    readonly #activityChanges = new ChangeNotificationSource();
    readonly #state = new SoAIBenchRunSessionState();
    readonly #selection = new SoAIBenchGpuSelection();
    readonly #resultActions: SoAIBenchResultActions;
    readonly #renderer: SoAIBenchRunModalRenderer;
    readonly #operations: SoAIBenchRunOperations;
    #activitySignature = '';

    constructor({ host, publishRun }: SoAIBenchRunModalDependencies) {
        this.host = host;
        this.#resultActions = new SoAIBenchResultActions({
            host,
            publishRun,
            resolveActionButton: (runId, action) => this.#renderer.resolveActionButton(runId, action),
            onPublicationChange: () => this.#renderer.schedule()
        });
        this.#renderer = new SoAIBenchRunModalRenderer({ host, modalId: this.modalId, state: this.#state, selection: this.#selection, resultActions: this.#resultActions, isDeviceBusy: (deviceId) => this.#isDeviceBusy(deviceId) });
        this.#operations = new SoAIBenchRunOperations({ host, state: this.#state, onChange: () => this.#changed() });
    }

    hasActivity(): boolean {
        return this.#state.hasActivity();
    }

    deviceActivity(deviceId: string | null): SoAIBenchActivityState | null {
        return this.#state.deviceActivity(deviceId);
    }

    subscribeActivity(listener: () => void): () => boolean {
        return this.#activityChanges.subscribe(listener);
    }

    hasRetainedRuns(): boolean {
        return this.#state.entries().length > 0;
    }

    setGpuOptions(options: readonly SoAIBenchRunOpenRequest[]): void {
        this.#state.gpuOptions = options;
    }

    setRunsFreshness(freshness: SoAIBenchRunsFreshness): void {
        this.#state.freshness = freshness;
        this.#renderer.schedule();
    }

    handleRunsUpdate(payload: JsonObject): void {
        this.#operations.reconcile(payload);
    }

    handleRunDeleted(runId: string): void {
        if (this.#state.removeRun(runId)) {
            this.#changed();
        }
    }

    open(): Promise<void> {
        return this.host.runWithBoundary('hardware:openSoAIBenchRunModal', async () => {
            if (!this.hasRetainedRuns()) {
                this.#showComposerForInventory();
            }
            this.#present(null);
        });
    }

    openForGpu(request: SoAIBenchRunOpenRequest): Promise<void> {
        return this.host.runWithBoundary('hardware:openSoAIBenchRunForGpu', async () => {
            const active = this.#state.activeEntryForDevice(request.deviceId);
            if (active === null) {
                this.#selection.showIntro(request);
            }
            this.#present(active === null ? () => this.#renderer.revealComposer() : () => this.#renderer.revealSection(active.sectionId));
        });
    }

    handleModalClosed(): void {
        this.#selection.close();
        this.#renderer.hide();
    }

    readonly handleScroll = (): void => {
        this.#renderer.captureScroll();
    };

    disposeForPageLifecycle(reason: string): void {
        this.#state.reset();
        this.#selection.close();
        this.#resultActions.reset();
        this.#renderer.reset();
        this.#activitySignature = '';
        if (this.host.modals.isOpen(this.modalId)) {
            this.host.modals.close(this.modalId, { force: true, restoreFocus: false, reason });
        }
    }

    showNewBenchmark(): Promise<void> {
        return this.host.runWithBoundary('hardware:showSoAIBenchComposer', async () => {
            this.#showComposerForInventory();
            this.#renderer.render();
            this.#renderer.revealComposer();
        });
    }

    dismissComposer(): Promise<void> {
        return this.host.runWithBoundary('hardware:dismissSoAIBenchComposer', async () => {
            this.#selection.dismiss();
            this.#renderer.render();
            if (this.#selection.composer.type === 'closed') {
                this.#renderer.focusNewBenchmark();
            } else {
                this.#renderer.revealComposer();
            }
        });
    }

    selectGpu(position: string): Promise<void> {
        return this.host.runWithBoundary('hardware:selectSoAIBenchGpu', async () => {
            this.#selection.select(position);
            this.#renderer.render();
            this.#renderer.revealComposer();
        });
    }

    startConfirmed(): Promise<void> {
        return this.host.runWithBoundary('hardware:confirmSoAIBenchStart', async () => {
            const request = this.#selection.requireIntroRequest();
            const started = this.#operations.start(request, null);
            this.#selection.close();
            this.#renderer.render();
            this.#revealDevice(request.deviceId);
            await started?.settled;
        });
    }

    retryStart(sectionId: string): Promise<void> {
        return this.host.runWithBoundary('hardware:retrySoAIBenchStart', async () => {
            const entry = this.#state.requireEntry(sectionId);
            const started = this.#operations.start(this.#state.currentRequest(entry), entry);
            this.#renderer.render();
            if (started === null) {
                this.#revealDevice(entry.request.deviceId);
            }
            await started?.settled;
        });
    }

    recoverRun(sectionId: string): Promise<void> {
        return this.#operations.recover(sectionId);
    }

    stopRun(runId: string): Promise<void> {
        return this.#operations.stop(runId);
    }

    runAgain(sectionId: string): Promise<void> {
        return this.host.runWithBoundary('hardware:runSoAIBenchAgain', async () => {
            this.#selection.showIntro(this.#state.currentRequest(this.#state.requireEntry(sectionId)));
            this.#renderer.render();
            this.#renderer.revealComposer();
        });
    }

    openHistory(sectionId: string | null): Promise<void> {
        return this.host.runWithBoundary('hardware:openSoAIBenchHistoryFromRunModal', async () => {
            const request = sectionId === null ? this.#selection.requireIntroRequest() : this.#state.requireEntry(sectionId).request;
            this.host.modals.close(this.modalId, { restoreFocus: false });
            await this.host.showSoAIBenchHistory(request);
        });
    }

    copyRun(runId: string): Promise<void> {
        return this.#resultActions.copy(() => this.#requireResult(runId, i18n.t('hardware.modals.soaibenchRun.copyUnavailable')));
    }

    downloadRun(runId: string): Promise<void> {
        return this.#resultActions.download(runId, () => this.#requireResult(runId, i18n.t('hardware.modals.soaibenchRun.copyUnavailable')));
    }

    publishRun(runId: string): Promise<void> {
        return this.#resultActions.publish(runId, () => this.#requireResult(runId, i18n.t('hardware.soaibenchPublication.unavailable')));
    }

    #requireResult(runId: string, unavailableMessage: string): SoAIBenchResultTarget {
        const entry = this.#state.requireRunEntry(runId);
        if (entry.run === null || resolveSoAIBenchRunPhase(entry) !== 'terminal') {
            throw new Error(unavailableMessage);
        }
        return { request: entry.request, run: entry.run };
    }

    #showComposerForInventory(): void {
        const options = this.#state.gpuOptions;
        const onlyOption = options[0];
        if (options.length === 1 && onlyOption !== undefined) {
            this.#selection.showIntro(onlyOption);
            return;
        }
        this.#selection.showPicker(options);
    }

    #isDeviceBusy(deviceId: string): boolean {
        return this.#state.deviceActivity(deviceId) !== null || findActiveRunForDevice(this.#state.runsPayload, deviceId) !== null;
    }

    #revealDevice(deviceId: string): void {
        const entry = this.#state.activeEntryForDevice(deviceId);
        if (entry !== null) {
            this.#renderer.revealSection(entry.sectionId);
        }
    }

    #present(afterOpen: (() => void) | null): void {
        const wasOpen = this.host.modals.isOpen(this.modalId);
        this.#renderer.show();
        if (wasOpen) {
            afterOpen?.();
            return;
        }
        this.host.modals.open(this.modalId);
        this.#renderer.restoreScroll();
        if (afterOpen !== null) {
            terminateHandledPromise(this.#afterInitialFocus(this.#state.visit, afterOpen));
        }
    }

    async #afterInitialFocus(visit: number, action: () => void): Promise<void> {
        await DomObserver.animationFrame();
        await DomObserver.animationFrame();
        if (this.#state.isVisitActive(visit) && this.host.modals.isOpen(this.modalId)) {
            action();
        }
    }

    #changed(): void {
        this.#renderer.schedule();
        const signature = this.#state.activitySignature();
        if (signature !== this.#activitySignature) {
            this.#activitySignature = signature;
            this.#activityChanges.notify();
        }
    }
}

export { SoAIBenchRunModal };
