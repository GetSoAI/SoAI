/* SoAI - File explorer page control layer task progress controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerTaskProgressController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { createTaskOperationPanel, type TaskOperationPanel } from '@core/tasks/operationpanel/service.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import type { TaskOperationEntry, TaskOperationsApi } from '@core/tasks/protocols.ts';
import { syncDeterminateProgress } from '@core/ui/progressWidths.ts';
import { FileExplorerTaskDisplayController } from '@pages/fileexplorer/controllers/fileExplorerTaskDisplayController.ts';
import { resolveFileExplorerTaskSummary, type FileExplorerTaskSnapshot } from '@pages/fileexplorer/controllers/fileExplorerTaskSummary.ts';
import type { FileExplorerUiRefs } from '@pages/fileexplorer/types.ts';

interface FileExplorerTaskProgressControllerDependencies {
    ui: FileExplorerUiRefs;
    onCancelTask: (taskId: string) => Promise<void>;
}

class FileExplorerTaskProgressController {
    readonly #ui: FileExplorerUiRefs;
    readonly #operationsApi: TaskOperationsApi;
    readonly #onCancelTask: (taskId: string) => Promise<void>;
    readonly #display: FileExplorerTaskDisplayController;
    readonly #operationPanel: TaskOperationPanel;
    readonly #recentUpdates = new Map<string, FileExplorerTaskSnapshot>();
    #trackedTaskIds = new Set<string>();
    #unsubscribe: (() => void) | null = null;
    #isExpanded = false;

    constructor(dependencies: FileExplorerTaskProgressControllerDependencies) {
        this.#ui = dependencies.ui;
        this.#onCancelTask = dependencies.onCancelTask;
        this.#operationsApi = requireTaskOperationsApi();
        this.#display = new FileExplorerTaskDisplayController(dependencies.ui, i18n.t('fileExplorer.labels.none'));
        this.#operationPanel = createTaskOperationPanel({
            container: dependencies.ui.taskProgress,
            filter: { types: ['file-explorer-op'] },
            operationsApi: this.#operationsApi,
            showCancel: true
        });
        this.#setExpanded(false);
        this.#syncOperations([]);
    }

    initialize(): void {
        this.destroy();
        this.#operationPanel.attach();
        this.#unsubscribe = this.#operationsApi.subscribeOperations({ types: ['file-explorer-op'] }, (operations) => {
            this.#syncOperations(operations);
        });
        void this.#operationsApi.reconcileOperations().catch((error) => {
            errorHandler.warn('FileExplorer', 'Task operation reconciliation failed', ensureError(error));
        });
    }

    destroy(): void {
        const unsubscribe = this.#unsubscribe;
        this.#unsubscribe = null;
        runCleanup(unsubscribe, (runtimeError) => {
            errorHandler.warn('FileExplorer', 'Task progress subscription cleanup failed', runtimeError);
        });
        this.#operationPanel.detach();
        this.#trackedTaskIds.clear();
        this.#recentUpdates.clear();
        this.#display.reset();
        this.#setExpanded(false);
        this.#syncOperations([]);
    }

    trackTask(taskId: string, label: string): void {
        const operationId = taskId.trim();
        if (!operationId) {
            return;
        }
        this.#operationsApi.upsertLocalOperation({
            id: operationId,
            type: 'file-explorer-op',
            meta: {
                displayName: label,
                statusMessage: label,
                taskType: 'file_explorer_op'
            },
            progress: 0,
            cancelable: true,
            cancel: () => this.#onCancelTask(operationId)
        });
    }

    toggleExpanded(): void {
        if (!this.#ui.taskPanel.classList.contains('u-hidden')) {
            this.#setExpanded(!this.#isExpanded);
        }
    }

    #syncOperations(operations: readonly TaskOperationEntry[]): void {
        this.#trackedTaskIds = new Set(operations.map((operation) => operation.id));
        this.#recentUpdates.clear();
        for (const operation of operations) {
            this.#recentUpdates.set(operation.id, {
                progress: typeof operation.progress === 'number' ? operation.progress : 0,
                message: this.#resolveOperationMessage(operation),
                details: this.#resolveOperationDetails(operation),
                state: 'info',
                at: Date.now()
            });
        }
        this.#syncTaskCount();
        this.#syncSummaryProgress();
    }

    #resolveOperationMessage(operation: TaskOperationEntry): string {
        const meta = operation.meta;
        const displayName = typeof meta?.['displayName'] === 'string' ? meta['displayName'].trim() : '';
        const statusMessage = typeof meta?.['statusMessage'] === 'string' ? meta['statusMessage'].trim() : '';
        return displayName || statusMessage || i18n.t('fileExplorer.labels.none');
    }

    #resolveOperationDetails(operation: TaskOperationEntry): string {
        const details = operation.meta?.['details'];
        return typeof details === 'string' ? details.trim() : '';
    }

    #syncTaskCount(): void {
        const taskCount = this.#trackedTaskIds.size;
        this.#ui.taskCount.textContent = String(taskCount);
        this.#ui.taskPanel.classList.toggle('u-hidden', taskCount <= 0);
        if (taskCount <= 0) {
            this.#setExpanded(false);
        }
    }

    #syncSummaryProgress(): void {
        const summary = resolveFileExplorerTaskSummary(this.#trackedTaskIds, this.#recentUpdates);
        this.#display.sync(summary.latestTaskId, summary.latestTaskLabel);
        syncDeterminateProgress({
            fillElement: this.#ui.taskSummaryBarFill,
            progress: summary.progress,
            progressbarElement: this.#ui.taskSummaryBar,
            valueElement: this.#ui.taskSummaryValue
        });
    }

    #setExpanded(expanded: boolean): void {
        this.#isExpanded = expanded;
        this.#ui.taskPanel.classList.toggle('is-expanded', expanded);
        this.#ui.taskPanel.classList.toggle('is-collapsed', !expanded);
        this.#ui.taskToggleButton.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        this.#ui.taskDetails.setAttribute('aria-hidden', expanded ? 'false' : 'true');
    }
}

export { FileExplorerTaskProgressController };
