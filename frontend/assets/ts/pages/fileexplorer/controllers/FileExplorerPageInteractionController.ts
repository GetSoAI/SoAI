/* SoAI - File explorer page control layer interaction controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerPageInteractionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { FILE_EXPLORER_ACTION_COPY_HERE, FILE_EXPLORER_ACTION_MODE_CANCEL, FILE_EXPLORER_ACTION_MOVE_HERE, FILE_EXPLORER_ACTION_NEW_ENTRY, FILE_EXPLORER_ACTION_REFRESH, FILE_EXPLORER_ACTION_ROW_OPEN, FILE_EXPLORER_ACTION_SELECT_ALL, FILE_EXPLORER_ACTION_SELECT_ROW, FILE_EXPLORER_ACTION_SORT, FILE_EXPLORER_ACTION_TASK_PANEL_TOGGLE, FILE_EXPLORER_ACTION_TOGGLE_VIEW_MODE, FILE_EXPLORER_ACTION_UPLOAD_FILES, isFileExplorerChangeActionId, isFileExplorerClickActionId } from '@features/fileexplorer/public.ts';
import type { FileExplorerCommandsController } from '@pages/fileexplorer/controllers/FileExplorerCommandsController.ts';
import type { FileExplorerBatchController } from '@pages/fileexplorer/controllers/FileExplorerBatchController.ts';
import type { FileExplorerDataController } from '@pages/fileexplorer/controllers/FileExplorerDataController.ts';
import type { FileExplorerOperationsController } from '@pages/fileexplorer/controllers/FileExplorerOperationsController.ts';
import type { FileExplorerNavigationHistoryController } from '@pages/fileexplorer/controllers/FileExplorerNavigationHistoryController.ts';
import { FileExplorerNewEntryController } from '@pages/fileexplorer/controllers/FileExplorerNewEntryController.ts';
import type { FileExplorerContentPreviewModalController } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewModalController.ts';
import { FileExplorerSelectionInteractionController } from '@pages/fileexplorer/controllers/FileExplorerSelectionInteractionController.ts';
import type { FileExplorerTaskProgressController } from '@pages/fileexplorer/controllers/FileExplorerTaskProgressController.ts';
import type { FileExplorerViewModeController } from '@pages/fileexplorer/controllers/FileExplorerViewModeController.ts';
import type { FileExplorerSelectionModel } from '@pages/fileexplorer/state/FileExplorerSelectionState.ts';

interface FileExplorerPageInteractionHost {
    showNotification: (message: string, type: NotificationType) => void;
    requireHTMLElement: (selector: string, context?: HTMLElement) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    runUiTask: (operation: string, task: () => Promise<void> | void) => Promise<void>;
}

const FILE_PREVIEW_LOADING_DELAY_MS = 250;

class FileExplorerPageInteractionController {
    readonly #host: FileExplorerPageInteractionHost;
    readonly #data: FileExplorerDataController;
    readonly #selection: FileExplorerSelectionModel;
    readonly #operations: FileExplorerOperationsController;
    readonly #batch: FileExplorerBatchController;
    readonly #commands: FileExplorerCommandsController;
    readonly #taskProgress: FileExplorerTaskProgressController;
    readonly #contentPreviewModal: FileExplorerContentPreviewModalController;
    readonly #viewMode: FileExplorerViewModeController;
    readonly #navigationHistory: FileExplorerNavigationHistoryController;
    readonly #selectionInteraction: FileExplorerSelectionInteractionController;
    readonly #newEntry: FileExplorerNewEntryController;
    readonly #resources = new ResourceTracker();
    #fileOpenSequence = 0;
    #loadingFileRow: HTMLElement | null = null;
    #disposed = false;

    constructor(dependencies: { host: FileExplorerPageInteractionHost; data: FileExplorerDataController; selection: FileExplorerSelectionModel; operations: FileExplorerOperationsController; batch: FileExplorerBatchController; commands: FileExplorerCommandsController; taskProgress: FileExplorerTaskProgressController; contentPreviewModal: FileExplorerContentPreviewModalController; viewMode: FileExplorerViewModeController; navigationHistory: FileExplorerNavigationHistoryController }) {
        this.#host = dependencies.host;
        this.#data = dependencies.data;
        this.#selection = dependencies.selection;
        this.#operations = dependencies.operations;
        this.#batch = dependencies.batch;
        this.#commands = dependencies.commands;
        this.#taskProgress = dependencies.taskProgress;
        this.#contentPreviewModal = dependencies.contentPreviewModal;
        this.#viewMode = dependencies.viewMode;
        this.#navigationHistory = dependencies.navigationHistory;
        this.#selectionInteraction = new FileExplorerSelectionInteractionController({
            host: dependencies.host,
            data: dependencies.data,
            selection: dependencies.selection,
            operations: dependencies.operations,
            batch: dependencies.batch,
            taskProgress: dependencies.taskProgress,
            commands: dependencies.commands
        });
        this.#newEntry = new FileExplorerNewEntryController({
            contentPreviewModal: dependencies.contentPreviewModal,
            operations: dependencies.operations,
            getCurrentPath: () => dependencies.data.getCurrentPath(),
            isDisposed: () => this.#disposed
        });
    }

    destroy(): void {
        this.#disposed = true;
        this.#fileOpenSequence += 1;
        this.#resources.cleanup();
        this.#clearFilePreviewLoading();
        this.#selectionInteraction.dispose();
    }

    dispatchRootClick(action: string, actionElement: HTMLElement): void {
        if (this.#disposed) return;
        if (!isFileExplorerClickActionId(action)) return;
        terminateHandledPromise(this.#runAction(`click:${action}`, async () => this.#handleClick(action, actionElement)));
    }

    dispatchRootChange(action: string, actionElement: HTMLElement): void {
        if (this.#disposed) return;
        if (!isFileExplorerChangeActionId(action)) return;
        terminateHandledPromise(this.#runAction(`change:${action}`, async () => this.#handleChange(action, actionElement)));
    }

    async #handleClick(action: string, actionElement: HTMLElement): Promise<void> {
        if (this.#disposed) return;
        if (action === FILE_EXPLORER_ACTION_TOGGLE_VIEW_MODE) {
            this.#viewMode.toggle();
            return;
        }
        if (action === FILE_EXPLORER_ACTION_REFRESH) {
            await this.#data.refreshList();
            if (this.#disposed) return;
            this.#host.showNotification(i18n.t('common.notifications.refreshCompleted'), 'refresh');
            return;
        }
        if (action === FILE_EXPLORER_ACTION_SORT) {
            const column = actionElement.dataset['sort'];
            if (!column) {
                throw new Error('Sort action element is missing required data-sort attribute');
            }
            await this.#data.sort(column);
            return;
        }
        if (action === FILE_EXPLORER_ACTION_ROW_OPEN) {
            const path = this.#requirePathData(actionElement);
            const isDirectory = actionElement.dataset['directory'] === '1';
            if (isDirectory) {
                if (actionElement.dataset['parentRow'] !== '1' && this.#selection.getSelectedPaths().length > 0) {
                    this.#selection.setPathSelected(path, true);
                    return;
                }
                await this.#navigationHistory.navigate(path);
                return;
            }
            await this.#openFilePreview(path, actionElement);
            return;
        }
        if (action === FILE_EXPLORER_ACTION_TASK_PANEL_TOGGLE) {
            this.#taskProgress.toggleExpanded();
            return;
        }
        if (action === FILE_EXPLORER_ACTION_MODE_CANCEL) {
            this.#commands.exitTransferMode();
            return;
        }
        if (await this.#selectionInteraction.handleClick(action)) {
            return;
        }
        if (action === FILE_EXPLORER_ACTION_COPY_HERE) {
            const taskId = await this.#batch.batchCopyTask(this.#commands.transferSources, this.#data.getCurrentPath());
            if (this.#disposed) return;
            if (taskId) {
                this.#taskProgress.trackTask(taskId, i18n.t('fileExplorer.taskPanel.copy'));
            }
            this.#commands.exitTransferMode();
            return;
        }
        if (action === FILE_EXPLORER_ACTION_MOVE_HERE) {
            const taskId = await this.#batch.batchMoveTask(this.#commands.transferSources, this.#data.getCurrentPath());
            if (this.#disposed) return;
            if (taskId) {
                this.#taskProgress.trackTask(taskId, i18n.t('fileExplorer.taskPanel.move'));
            }
            this.#commands.exitTransferMode();
            return;
        }
    }

    async #handleChange(action: string, actionElement: HTMLElement): Promise<void> {
        if (this.#disposed) return;
        if (action === FILE_EXPLORER_ACTION_SELECT_ALL) {
            if (!(actionElement instanceof HTMLInputElement)) {
                throw new TypeError('Select-all action requires checkbox input');
            }
            if (actionElement.checked) {
                this.#selection.selectAll();
            } else {
                this.#selection.deselectAll();
            }
            return;
        }
        if (action === FILE_EXPLORER_ACTION_SELECT_ROW) {
            if (!(actionElement instanceof HTMLInputElement)) {
                throw new TypeError('Row select action requires checkbox input');
            }
            this.#selection.setPathSelected(this.#requirePathData(actionElement), actionElement.checked);
            return;
        }
        if (action === FILE_EXPLORER_ACTION_NEW_ENTRY) {
            if (!(actionElement instanceof HTMLSelectElement)) {
                throw new TypeError('New entry action requires a select control');
            }
            await this.#newEntry.run(actionElement);
            return;
        }
        if (action === FILE_EXPLORER_ACTION_UPLOAD_FILES) {
            if (!(actionElement instanceof HTMLInputElement)) {
                throw new TypeError('Upload action requires file input');
            }
            if (actionElement.files && actionElement.files.length > 0) {
                await this.#operations.uploadFiles(actionElement.files);
            }
            if (this.#disposed) return;
            actionElement.value = '';
            return;
        }
    }

    #requirePathData(element: HTMLElement): string {
        const value = element.dataset['path'];
        if (!value || !value.trim()) {
            const action = element.dataset['action'];
            if (!action || !action.trim()) {
                throw new Error('Missing data-path and action on file explorer control');
            }
            throw new Error(`Missing data-path for action ${action}`);
        }
        return value;
    }

    async #openFilePreview(path: string, row: HTMLElement): Promise<void> {
        this.#clearFilePreviewLoading();
        const sequence = ++this.#fileOpenSequence;
        const loadingTimerId = this.#resources.setTimeout(() => {
            if (this.#disposed || this.#fileOpenSequence !== sequence) {
                return;
            }
            row.dataset['filePreviewLoading'] = 'true';
            row.setAttribute('aria-busy', 'true');
            this.#loadingFileRow = row;
        }, FILE_PREVIEW_LOADING_DELAY_MS);
        try {
            await this.#contentPreviewModal.show(path);
        } finally {
            this.#resources.clearTimeout(loadingTimerId);
            if (this.#fileOpenSequence === sequence) {
                this.#clearFilePreviewLoading();
            }
        }
    }

    #clearFilePreviewLoading(): void {
        if (!this.#loadingFileRow) {
            return;
        }
        delete this.#loadingFileRow.dataset['filePreviewLoading'];
        this.#loadingFileRow.removeAttribute('aria-busy');
        this.#loadingFileRow = null;
    }

    async #runAction(operation: string, task: () => Promise<void> | void): Promise<void> {
        if (this.#disposed) return;
        await this.#host.runUiTask(`fileExplorer:${operation}`, async () => {
            if (this.#disposed) return;
            await task();
        });
    }
}
export { FileExplorerPageInteractionController };
