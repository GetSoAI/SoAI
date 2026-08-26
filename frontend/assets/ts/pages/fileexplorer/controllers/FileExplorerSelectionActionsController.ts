/* SoAI - File explorer page control layer selection actions controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerSelectionActionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { replaceChildrenFromHtml } from '@core/dom/html.ts';
import { basenameVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { FileBrowserMetadata } from '@core/fileexplorerbrowser/types.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { securityApi } from '@core/security/public.ts';
import { buildSoaiPathToken } from '@core/soailinks/codec.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { copyTextWithBrowserClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { FILE_EXPLORER_ACTION_METADATA_COPY, FILE_EXPLORER_METADATA_MODAL_ID } from '@features/fileexplorer/public.ts';
import type { FileExplorerBatchController } from '@pages/fileexplorer/controllers/FileExplorerBatchController.ts';
import type { FileExplorerCommandsController } from '@pages/fileexplorer/controllers/FileExplorerCommandsController.ts';
import type { FileExplorerDataController } from '@pages/fileexplorer/controllers/FileExplorerDataController.ts';
import type { FileExplorerOperationsController } from '@pages/fileexplorer/controllers/FileExplorerOperationsController.ts';
import type { FileExplorerTaskProgressController } from '@pages/fileexplorer/controllers/FileExplorerTaskProgressController.ts';
import type { FileExplorerSelectionModel } from '@pages/fileexplorer/state/FileExplorerSelectionState.ts';
import { filenameFromPath, normalizeFileExplorerRenameLeaf, validateFileExplorerRenameLeaf, type FileExplorerRenameLeafError } from '@pages/fileexplorer/controllers/fileExplorerOperations.ts';
import { renderMetadataMarkup } from '@pages/fileexplorer/rendering/FileExplorerMetadataMarkupWidget.ts';

interface SelectionActionsHost {
    showNotification: (message: string, type: NotificationType) => void;
    requireHTMLElement: (selector: string, context?: HTMLElement) => HTMLElement;
    modalPresenter: ModalPresenterApi;
}

const METADATA_MODAL_ID = FILE_EXPLORER_METADATA_MODAL_ID;
const { guard: isMetadataCopyAction } = createActionIdSet(FILE_EXPLORER_ACTION_METADATA_COPY);

const resolveRenameLeafValidationMessage = (error: FileExplorerRenameLeafError): string => {
    if (error === 'required') {
        return i18n.t('fileExplorer.errors.renameNameRequired');
    }
    if (error === 'unchanged') {
        return i18n.t('fileExplorer.errors.renameNameUnchanged');
    }
    if (error === 'pathSeparator') {
        return i18n.t('fileExplorer.errors.renameNamePathSeparator');
    }
    return i18n.t('fileExplorer.errors.renameNameInvalid');
};

class FileExplorerSelectionActionsController {
    readonly #host: SelectionActionsHost;
    readonly #data: FileExplorerDataController;
    readonly #selection: FileExplorerSelectionModel;
    readonly #operations: FileExplorerOperationsController;
    readonly #batch: FileExplorerBatchController;
    readonly #taskProgress: FileExplorerTaskProgressController;
    readonly #commands: FileExplorerCommandsController;
    readonly #resources = new ResourceTracker();
    #metadataCopyWired = false;
    #disposed = false;
    #downloadInProgress = false;

    constructor(dependencies: { host: SelectionActionsHost; data: FileExplorerDataController; selection: FileExplorerSelectionModel; operations: FileExplorerOperationsController; batch: FileExplorerBatchController; taskProgress: FileExplorerTaskProgressController; commands: FileExplorerCommandsController }) {
        this.#host = dependencies.host;
        this.#data = dependencies.data;
        this.#selection = dependencies.selection;
        this.#operations = dependencies.operations;
        this.#batch = dependencies.batch;
        this.#taskProgress = dependencies.taskProgress;
        this.#commands = dependencies.commands;
    }

    async showMetadataForSelection(): Promise<void> {
        if (this.#disposed) return;
        const selection = this.#requireSelection();
        if (selection === null) return;

        const modalRoot = this.#host.modalPresenter.requireElement(METADATA_MODAL_ID);
        this.#ensureMetadataCopyWired(modalRoot);
        const body = this.#host.requireHTMLElement(modalUiSelector(METADATA_MODAL_ID, 'body'), modalRoot);
        if (selection.length === 1) {
            const path = selection[0];
            if (typeof path !== 'string' || !path.trim()) {
                throw new Error('File Explorer selection path is invalid');
            }
            const metadata = await this.#data.loadMetadata(path);
            if (this.#disposed) return;
            replaceChildrenFromHtml({ element: body, html: securityApi.sanitizeHtml(renderMetadataMarkup(metadata)), context: body });
            this.#host.modalPresenter.open(METADATA_MODAL_ID);
            return;
        }

        const metadatas: FileBrowserMetadata[] = [];
        for (const path of selection) {
            const metadata = await this.#data.loadMetadata(path);
            if (this.#disposed) return;
            metadatas.push(metadata);
        }
        const sections = metadatas
            .map((metadata) => {
                const title = securityApi.escapeHtml(metadata.path);
                const details = renderMetadataMarkup(metadata);
                return `<div class="file-explorer-metadata-section"><h4>${title}</h4>${details}</div>`;
            })
            .join('');
        replaceChildrenFromHtml({
            element: body,
            html: securityApi.sanitizeHtml(`<div class="file-explorer-metadata-batch-intro">${securityApi.escapeHtml(i18n.t('fileExplorer.actionBar.metadata.batch', { count: metadatas.length }))}</div>${sections}`),
            context: body
        });
        this.#host.modalPresenter.open(METADATA_MODAL_ID);
    }

    async downloadSelection(): Promise<void> {
        if (this.#disposed || this.#downloadInProgress) return;
        const selection = this.#requireSelection();
        if (selection === null) return;
        const normalizedSelection: string[] = [];
        for (const path of selection) {
            if (typeof path !== 'string' || !path.trim()) {
                throw new Error('File Explorer download selection path is invalid');
            }
            normalizedSelection.push(path);
        }
        const abortController = this.#resources.track(new AbortController(), (controller) => controller.abort());
        this.#downloadInProgress = true;
        let clearLoading: (() => void) | null = null;
        try {
            clearLoading = this.#commands.beginSelectionDownload();
            if (normalizedSelection.length === 1) {
                const selectedPath = normalizedSelection[0];
                if (!selectedPath) {
                    throw new Error('File Explorer download selection path is unavailable');
                }
                await this.#operations.downloadPath(selectedPath, { signal: abortController.signal });
                return;
            }
            await this.#operations.downloadSelection(normalizedSelection, { signal: abortController.signal });
        } finally {
            this.#resources.untrack(abortController);
            try {
                clearLoading?.();
            } finally {
                this.#downloadInProgress = false;
            }
        }
    }

    async deleteSelection(): Promise<void> {
        if (this.#disposed) return;
        const selection = this.#requireSelection();
        if (selection === null) return;
        if (selection.length === 1) {
            const path = selection[0];
            if (typeof path !== 'string' || !path.trim()) {
                throw new Error('File Explorer selection path is invalid');
            }
            await this.#operations.deletePath(path);
            return;
        }
        const taskId = await this.#batch.batchDeleteTask(selection);
        if (this.#disposed) return;
        if (taskId) {
            this.#taskProgress.trackTask(taskId, i18n.t('fileExplorer.taskPanel.delete'));
        }
    }

    async renameSelection(): Promise<void> {
        if (this.#disposed) return;
        const snapshot = this.#selection.snapshot();
        if (snapshot.selectedPaths.length !== 1) {
            throw new Error('File Explorer rename requires exactly one selected entry');
        }
        const sourcePath = snapshot.selectedPaths[0];
        if (typeof sourcePath !== 'string' || !sourcePath.trim()) {
            throw new Error('File Explorer rename selection path is invalid');
        }
        const currentLeaf = filenameFromPath(sourcePath);
        const renamedLeaf = await requireDialogsService().showPrompt({
            title: i18n.t('fileExplorer.modals.rename.title'),
            message: i18n.t('fileExplorer.modals.rename.nameLabel'),
            defaultValue: currentLeaf,
            placeholder: currentLeaf,
            confirmText: i18n.t('common.save'),
            validate: (value: string): string | null => {
                const error = validateFileExplorerRenameLeaf(value, currentLeaf);
                return error === null ? null : resolveRenameLeafValidationMessage(error);
            }
        });
        if (renamedLeaf === null || this.#disposed) {
            return;
        }
        if (!this.#selection.isSnapshotCurrent(snapshot)) {
            this.#host.showNotification(i18n.t('fileExplorer.errors.selectionChanged'), 'warning');
            return;
        }
        const validationError = validateFileExplorerRenameLeaf(renamedLeaf, currentLeaf);
        if (validationError !== null) {
            throw new Error('File Explorer rename prompt returned an invalid filename');
        }
        await this.#operations.renamePath(sourcePath, normalizeFileExplorerRenameLeaf(renamedLeaf));
    }

    async copySoaiLinkForSelection(): Promise<void> {
        if (this.#disposed) return;
        const selection = this.#requireSelection();
        if (selection === null) return;
        const tokens = selection.map((path) => {
            if (typeof path !== 'string' || !path.trim()) {
                throw new Error('File Explorer SoAI link selection path is invalid');
            }
            const virtualPath = toVirtualPath(path);
            return buildSoaiPathToken({
                virtualPath,
                label: basenameVirtualPath(virtualPath)
            });
        });
        await copyTextWithBrowserClipboardFeedback(
            {
                showNotification: (message, type): void => {
                    if (!this.#disposed) {
                        this.#host.showNotification(message, type);
                    }
                }
            },
            {
                text: tokens.join('\n'),
                successMessage: i18n.t('fileExplorer.modal.soaiLinkCopySuccess'),
                errorMessage: i18n.t('fileExplorer.modal.soaiLinkCopyFailed'),
                unavailableMessage: i18n.t('fileExplorer.modal.soaiLinkCopyFailed'),
                unavailableType: 'error'
            }
        );
    }

    dispose(): void {
        this.#disposed = true;
        this.#resources.cleanup();
    }

    #requireSelection(): readonly string[] | null {
        const selection = this.#selection.getSelectedPaths();
        if (selection.length <= 0) {
            this.#host.showNotification(i18n.t('fileExplorer.errors.selectionRequired'), 'error');
            return null;
        }
        return selection;
    }

    #ensureMetadataCopyWired(modalRoot: HTMLElement): void {
        if (this.#metadataCopyWired) {
            return;
        }
        const abortController = this.#resources.track(new AbortController(), (controller) => controller.abort());
        bindPageActionDispatcher({
            root: modalRoot,
            signal: abortController.signal,
            label: 'FileExplorer.metadataModal',
            isAction: isMetadataCopyAction,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'always',
                    stopPropagation: true,
                    onAction: ({ actionElement }): void => {
                        if (!(actionElement instanceof HTMLButtonElement)) {
                            throw new TypeError('File Explorer metadata copy action must be a button');
                        }
                        terminateHandledPromise(this.#copyMetadataToClipboard(modalRoot));
                    }
                }
            }
        });
        this.#metadataCopyWired = true;
    }

    async #copyMetadataToClipboard(modalRoot: HTMLElement): Promise<void> {
        const body = this.#host.requireHTMLElement(modalUiSelector(METADATA_MODAL_ID, 'body'), modalRoot);
        await copyTextWithBrowserClipboardFeedback(
            {
                showNotification: (message, type): void => {
                    if (!this.#disposed) {
                        this.#host.showNotification(message, type);
                    }
                }
            },
            {
                text: body.textContent ?? '',
                successMessage: i18n.t('fileExplorer.modal.metadataCopySuccess'),
                errorMessage: i18n.t('fileExplorer.modal.metadataCopyFailed'),
                unavailableMessage: i18n.t('fileExplorer.modal.metadataCopyFailed'),
                unavailableType: 'error'
            }
        );
    }
}

export { FileExplorerSelectionActionsController };
