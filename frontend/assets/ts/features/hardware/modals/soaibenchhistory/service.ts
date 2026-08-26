/* SoAI - SoAI Bench history modal service [frontend/assets/ts/features/hardware/modals/soaibenchhistory/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { decodeGpuOperationResponse } from '@core/api/contracts/hardwareContracts.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { i18n } from '@core/i18n/index.ts';
import { HARDWARE } from '@core/realtime/streammanager/resources/ids.ts';
import { requireSortableColumn } from '@core/ui/tables/sortableTable.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { serializeGpuSoAIBenchHistoryRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import { HARDWARE_SOAIBENCH_HISTORY_MODAL_ID } from '@features/hardware/modals/constants.ts';
import { copySoAIBenchRunExport, downloadSoAIBenchRunExport } from '@features/hardware/modals/soaibenchrun/exportActions.ts';
import { exportRunFromHistoryRun } from '@features/hardware/modals/soaibenchrun/exportText.ts';
import { renderHistoryRows, resetHistoryState, setFooterActionsDisabled, setLoadingVisible, syncSortIndicators } from '@features/hardware/modals/soaibenchhistory/dom.ts';
import { formatHistoryRows } from '@features/hardware/modals/soaibenchhistory/formatting.ts';
import { formatSoAIBenchHistoryMarkdown } from '@features/hardware/modals/soaibenchhistory/markdown.ts';
import { normalizeHistoryRuns } from '@features/hardware/modals/soaibenchhistory/mappers.ts';
import { HISTORY_SORT_COLUMNS, HISTORY_SORT_DEFAULT_STATE, resolveNextHistorySortState, sortHistoryRuns, type SoAIBenchHistorySortState } from '@features/hardware/modals/soaibenchhistory/sorting.ts';
import type { SoAIBenchHistoryModalDependencies, SoAIBenchHistoryModalHost, SoAIBenchHistoryOpenRequest, SoAIBenchHistoryRun } from '@features/hardware/modals/soaibenchhistory/types.ts';

const HISTORY_LIMIT = 25;

class SoAIBenchHistoryModal {
    readonly modalId = HARDWARE_SOAIBENCH_HISTORY_MODAL_ID;
    readonly host: SoAIBenchHistoryModalHost;
    readonly #openToken = new SequenceToken();
    #request: SoAIBenchHistoryOpenRequest | null = null;
    #runs: readonly SoAIBenchHistoryRun[] = [];
    #sortState: SoAIBenchHistorySortState = HISTORY_SORT_DEFAULT_STATE;

    constructor({ host }: SoAIBenchHistoryModalDependencies) {
        if (!host) {
            throw new Error('SoAIBenchHistoryModal requires a host');
        }
        this.host = host;
    }

    handleModalClosed(): void {
        this.#openToken.invalidate();
        this.#request = null;
        this.#runs = [];
        this.#sortState = HISTORY_SORT_DEFAULT_STATE;
    }

    handleSortAction(header: HTMLElement): void {
        const sortColumn = requireSortableColumn(HISTORY_SORT_COLUMNS, header.dataset['sort'] ?? '', 'SoAIBench history');
        this.#sortState = resolveNextHistorySortState(this.#sortState, sortColumn);
        const modalRoot = this.host.modals.requireElement(this.modalId);
        if (!this.#runs.length) {
            syncSortIndicators(this.host, modalRoot, this.#sortState);
            return;
        }
        this.#renderRows(modalRoot);
    }

    async open(request: SoAIBenchHistoryOpenRequest): Promise<void> {
        return this.host.runWithBoundary('hardware:openSoAIBenchHistoryModal', async () => {
            const modalRoot = this.host.modals.requireElement(this.modalId);
            const openToken = this.#openToken.next();
            this.#request = request;
            this.#runs = [];
            this.#sortState = HISTORY_SORT_DEFAULT_STATE;
            resetHistoryState(this.host, modalRoot);
            setFooterActionsDisabled(this.host, modalRoot, true);
            this.host.modals.open(this.modalId);

            try {
                const result = decodeGpuOperationResponse(await requestWebSocketSnapshotRecord('hardware.gpu.soaibench.history', serializeGpuSoAIBenchHistoryRequest(request.deviceId, HISTORY_LIMIT)));
                if (!this.#openToken.isActive(openToken)) {
                    return;
                }
                this.#runs = normalizeHistoryRuns(result);
                this.#renderRows(modalRoot);
                setLoadingVisible(this.host, modalRoot, false);
                setFooterActionsDisabled(this.host, modalRoot, false);
            } catch (error) {
                if (!this.#openToken.isActive(openToken)) {
                    return;
                }
                setLoadingVisible(this.host, modalRoot, false);
                setFooterActionsDisabled(this.host, modalRoot, true);
                throw error;
            }
        });
    }

    async copy(): Promise<void> {
        return this.host.runWithBoundary('hardware:copySoAIBenchHistory', async () => {
            const request = this.#request;
            if (!request) {
                this.host.showNotification(i18n.t('hardware.modals.soaibenchHistory.copyUnavailable'), 'error');
                return;
            }
            const [systemInfo, hardware] = await Promise.all([requestWebSocketSnapshotRecord('system.info'), requestWebSocketSnapshotRecord(HARDWARE)]);
            const text = formatSoAIBenchHistoryMarkdown({
                request,
                runCount: this.#runs.length,
                rows: formatHistoryRows(this.#getSortedRuns()),
                systemInfo,
                hardware
            });
            await copyTextWithHostClipboardFeedback(
                {
                    copyToClipboard: (value, options) => this.host.copyToClipboard(value, options?.notify ? { notify: options.notify } : undefined),
                    hasClipboardSupport: () => this.host.hasClipboardSupport(),
                    showNotification: (message, type, duration): void => this.host.showNotification(message, type, duration)
                },
                {
                    text,
                    successMessage: i18n.t('hardware.modals.soaibenchHistory.copySuccess'),
                    unavailableMessage: i18n.t('hardware.modals.soaibenchHistory.copyUnavailable'),
                    unavailableType: 'error'
                }
            );
        });
    }

    async copyRun(runId: string): Promise<void> {
        return this.host.runWithBoundary('hardware:copySoAIBenchHistoryRun', async () => {
            const request = this.#requireRequest();
            await copySoAIBenchRunExport({
                host: this.host,
                request,
                run: exportRunFromHistoryRun(this.#requireRun(runId))
            });
        });
    }

    async downloadRun(runId: string): Promise<void> {
        return this.host.runWithBoundary('hardware:downloadSoAIBenchHistoryRun', async () => {
            downloadSoAIBenchRunExport({
                host: this.host,
                request: this.#requireRequest(),
                run: exportRunFromHistoryRun(this.#requireRun(runId))
            });
        });
    }

    async download(): Promise<void> {
        return this.host.runWithBoundary('hardware:downloadSoAIBenchHistoryCsv', async () => {
            const request = this.#requireRequest();
            const response = await this.host.downloadHistoryCsv(request.deviceId);
            await downloadAuthenticatedResponse(response);
            this.host.showNotification(i18n.t('hardware.modals.soaibenchHistory.downloadSuccess'), 'download');
        });
    }

    #renderRows(modalRoot: HTMLElement): void {
        renderHistoryRows(this.host, modalRoot, formatHistoryRows(this.#getSortedRuns()), this.#sortState);
    }

    #getSortedRuns(): SoAIBenchHistoryRun[] {
        return sortHistoryRuns(this.#runs, this.#sortState);
    }

    #requireRequest(): SoAIBenchHistoryOpenRequest {
        const request = this.#request;
        if (!request) {
            throw new Error(i18n.t('hardware.modals.soaibenchHistory.copyUnavailable'));
        }
        return request;
    }

    #requireRun(runId: string): SoAIBenchHistoryRun {
        const run = this.#runs.find((candidate) => candidate.runId === runId) ?? null;
        if (!run) {
            throw new Error(i18n.t('hardware.modals.soaibenchHistory.rowCopyUnavailable'));
        }
        return run;
    }
}

export { SoAIBenchHistoryModal };
