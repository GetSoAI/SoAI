/* SoAI - Hardware feature renderer [frontend/assets/ts/features/hardware/modals/soaibenchrun/renderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createOperationProgressReporter } from '@core/operationprogress/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireRunBody, setExportButtonState, setHistoryButtonState, setStartButtonState, type SoAIBenchRunFooterActionMode } from '@features/hardware/modals/soaibenchrun/dom.ts';
import { isTerminalSoAIBenchStatus } from '@features/hardware/modals/soaibenchrun/mappers.ts';
import type { SoAIBenchRunModalHost, SoAIBenchRunOpenRequest, SoAIBenchRunProgressRuntime, SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';
import { progressDetailsForRun, progressMessageForRun, progressPercentForRun, renderRunIntro, renderRunProgressShell, renderRunReport } from '@features/hardware/modals/soaibenchrun/view.ts';

const RUN_PROGRESS_KEY = 'hardware-soaibench-run';

const isExportableRun = (run: SoAIBenchRunRecord | null): boolean => {
    return run !== null && isTerminalSoAIBenchStatus(run.status);
};

interface SoAiBenchRunRendererDependencies {
    host: SoAIBenchRunModalHost;
    modalId: string;
    onCancel: () => Promise<void>;
}

interface SoAIBenchRunRenderRequest {
    request: SoAIBenchRunOpenRequest;
    run: SoAIBenchRunRecord | null;
    cancelRequested: boolean;
    terminalReason: string | null;
    runId: string | null;
    historyAvailable: boolean;
}

class SoAIBenchRunModalRenderer {
    readonly #host: SoAIBenchRunModalHost;
    readonly #modalId: string;
    readonly #onCancel: () => Promise<void>;
    readonly #progress: SoAIBenchRunProgressRuntime = { reporter: null };

    constructor(dependencies: SoAiBenchRunRendererDependencies) {
        this.#host = dependencies.host;
        this.#modalId = dependencies.modalId;
        this.#onCancel = dependencies.onCancel;
    }

    renderIntro(request: SoAIBenchRunOpenRequest, historyAvailable: boolean): void {
        this.destroyProgress();
        const modalRoot = this.#modalRoot();
        this.#host.setHTML(requireRunBody(this.#host, modalRoot), renderRunIntro({ request, run: null, cancelRequested: false, terminalReason: null }));
        this.#setFooterButton('start', false);
        setHistoryButtonState(this.#host, modalRoot, { visible: historyAvailable, disabled: false });
        setExportButtonState(this.#host, modalRoot, false);
    }

    renderProgress(inputArguments: SoAIBenchRunRenderRequest): void {
        const modalRoot = this.#modalRoot();
        this.destroyProgress();
        this.#host.setHTML(requireRunBody(this.#host, modalRoot), renderRunProgressShell({ request: inputArguments.request, run: inputArguments.run, cancelRequested: inputArguments.cancelRequested, terminalReason: null }));
        this.#setFooterButton(inputArguments.cancelRequested ? 'stopping' : 'stop', !(inputArguments.run?.runId || inputArguments.runId) || inputArguments.cancelRequested);
        setHistoryButtonState(this.#host, modalRoot, { visible: inputArguments.historyAvailable, disabled: false });
        setExportButtonState(this.#host, modalRoot, isExportableRun(inputArguments.run));
        const container = this.#host.requireHTMLElement('#hardware-soaibench-run-modal-progress', modalRoot);
        this.#progress.reporter = createOperationProgressReporter(container, {
            showCancel: true,
            showBadge: false,
            extraClassName: 'hardware-soaibench-progress',
            onCancel: async () => {
                await this.#onCancel();
            }
        });
        this.#progress.reporter.update(RUN_PROGRESS_KEY, {
            message: progressMessageForRun(inputArguments.run, inputArguments.cancelRequested),
            details: progressDetailsForRun(inputArguments.run),
            progress: progressPercentForRun(inputArguments.run),
            state: inputArguments.cancelRequested ? 'pending' : 'downloading',
            cancelable: Boolean(inputArguments.run?.runId || inputArguments.runId) && !inputArguments.cancelRequested
        });
    }

    renderReport(inputArguments: SoAIBenchRunRenderRequest): void {
        this.destroyProgress();
        const modalRoot = this.#modalRoot();
        this.#host.setHTML(requireRunBody(this.#host, modalRoot), renderRunReport({ request: inputArguments.request, run: inputArguments.run, cancelRequested: false, terminalReason: inputArguments.terminalReason }));
        this.#setFooterButton('start', false);
        setHistoryButtonState(this.#host, modalRoot, { visible: inputArguments.historyAvailable, disabled: false });
        setExportButtonState(this.#host, modalRoot, isExportableRun(inputArguments.run));
    }

    setHistoryAvailable(available: boolean): void {
        setHistoryButtonState(this.#host, this.#modalRoot(), { visible: available, disabled: false });
    }

    destroyProgress(): void {
        this.#progress.reporter?.destroy();
        this.#progress.reporter = null;
    }

    #modalRoot(): HTMLElement {
        return this.#host.modals.requireElement(this.#modalId);
    }

    #setFooterButton(mode: SoAIBenchRunFooterActionMode, disabled: boolean): void {
        const modalRoot = this.#modalRoot();
        const label = mode === 'start' ? i18n.t('hardware.modals.soaibenchRun.start') : mode === 'stop' ? i18n.t('hardware.modals.soaibenchRun.stop') : i18n.t('hardware.modals.soaibenchRun.stopping');
        const ariaLabel = mode === 'start' ? i18n.t('hardware.modals.soaibenchRun.ariaLabels.start') : mode === 'stop' ? i18n.t('hardware.modals.soaibenchRun.ariaLabels.stop') : i18n.t('hardware.modals.soaibenchRun.ariaLabels.stopping');
        setStartButtonState(this.#host, modalRoot, { hidden: false, disabled, mode, label, ariaLabel });
    }
}

export { SoAIBenchRunModalRenderer };
export type { SoAIBenchRunRenderRequest, SoAiBenchRunRendererDependencies };
