/* SoAI - File Explorer single-path operations controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerOperationsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerBatchUploadResponse, FileExplorerUploadResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { resolveOperationCauseMessage } from '@core/errors/operationCausePresentation.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { joinVirtualPath, parentVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { i18n } from '@core/i18n/index.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { FILE_EXPLORER_HTTP_STATUS_MESSAGES } from '@core/api/statusMessageCatalog.ts';
import { createDedupingOperationFailureReporter, type DedupingOperationFailureReporter } from '@core/ui/notifications/operationFailure.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { notifyFileExplorerHttpError } from '@pages/fileexplorer/controllers/fileExplorerHttpErrorController.ts';
import { filenameFromPath, normalizeFileExplorerRenameLeaf, toFiles, validateFileExplorerRenameLeaf } from '@pages/fileexplorer/controllers/fileExplorerOperations.ts';
import type { FileExplorerRecentUploadController } from '@pages/fileexplorer/controllers/FileExplorerRecentUploadController.ts';
import type { FileExplorerSelectionModel } from '@pages/fileexplorer/state/FileExplorerSelectionState.ts';
import type { FileExplorerControllerHost, FileExplorerSelectionProvider, FileExplorerUploadMarkerSession, FileExplorerUploadUi } from '@pages/fileexplorer/types.ts';

type FileExplorerDeletionOutcome = 'committed' | 'cancelled' | 'failed';

class FileExplorerOperationsController {
    #host: FileExplorerControllerHost;
    #ui: FileExplorerUploadUi;
    #selection: FileExplorerSelectionProvider;
    readonly #selectionModel: FileExplorerSelectionModel;
    #recentUploads: FileExplorerRecentUploadController;
    readonly #operationFailures: DedupingOperationFailureReporter;
    #disposed = false;

    constructor(dependencies: { host: FileExplorerControllerHost; ui: FileExplorerUploadUi; selection: FileExplorerSelectionProvider; selectionModel: FileExplorerSelectionModel; recentUploads: FileExplorerRecentUploadController }) {
        this.#host = dependencies.host;
        this.#ui = dependencies.ui;
        this.#selection = dependencies.selection;
        this.#selectionModel = dependencies.selectionModel;
        this.#recentUploads = dependencies.recentUploads;
        this.#operationFailures = createDedupingOperationFailureReporter({ host: dependencies.host });
    }

    openUploadPicker(options?: { directory?: boolean }): void {
        this.#requireActive();
        const wantsDirectory = options?.directory === true;
        if (wantsDirectory) {
            this.#ui.uploadFolderInput.click();
            return;
        }
        this.#ui.uploadFilesInput.click();
    }

    destroy(): void {
        this.#disposed = true;
    }

    async uploadFiles(files: FileList): Promise<void> {
        try {
            this.#requireActive();
            const fileList = toFiles(files);
            const destinationPath = this.#selection.getCurrentPath();
            const uploadSession = this.#recentUploads.beginUploadSession();
            const relativePaths = fileList.map((file) => {
                const relative = file.webkitRelativePath;
                if (typeof relative === 'string' && relative.trim()) {
                    return relative.trim();
                }
                return file.name;
            });
            const hasDirectoryHierarchy = relativePaths.some((relativePath) => relativePath.includes('/'));
            let response: FileExplorerUploadResponse | FileExplorerBatchUploadResponse;
            if (fileList.length === 1 && !hasDirectoryHierarchy) {
                const file = fileList[0];
                if (!file) throw new Error('Upload file is required');
                response = await this.#host.api.upload(file, destinationPath);
            } else {
                response = await this.#host.api.uploadBatch(fileList, relativePaths, destinationPath);
            }
            if (this.#disposed) {
                return;
            }
            const uploadMarked = this.#recentUploads.markUploadResponse(uploadSession, response);
            if ('failed' in response && response.failed > 0) {
                const causes = [
                    ...new Set(
                        response.results
                            .filter((result) => !result.success)
                            .map((result) => resolveOperationCauseMessage(result.code ?? null))
                            .filter((message) => message !== null)
                    )
                ].join(' ');
                if (response.succeeded > 0) {
                    this.#host.showNotification([i18n.t('fileExplorer.notifications.uploadPartial', { succeeded: response.succeeded, failed: response.failed }), causes].filter(Boolean).join(' '), 'warning');
                } else {
                    this.#host.showNotification([i18n.t('fileExplorer.notifications.uploadFailed', { succeeded: response.succeeded, failed: response.failed }), causes].filter(Boolean).join(' '), 'error');
                }
            } else {
                const uploadedCount = 'succeeded' in response ? response.succeeded : 1;
                this.#host.showNotification(i18n.t('fileExplorer.notifications.uploadSuccess', { count: uploadedCount }), 'success');
            }
            await this.#refreshRetainingMarks(uploadSession, uploadMarked);
        } catch (error) {
            if (this.#disposed) {
                return;
            }
            this.#handleError(ensureError(error), 'File Explorer upload failed');
        }
    }

    async createDirectory(path: string): Promise<void> {
        try {
            this.#requireActive();
            const normalized = toVirtualPath(path);
            const uploadSession = this.#recentUploads.beginUploadSession();
            await this.#host.api.mkdir(normalized);
            if (this.#disposed) {
                return;
            }
            const directoryMarked = this.#recentUploads.markCreatedPath(uploadSession, normalized);
            this.#host.showNotification(i18n.t('fileExplorer.notifications.mkdirSuccess', { path: normalized }), 'success');
            await this.#refreshRetainingMarks(uploadSession, directoryMarked);
        } catch (error) {
            if (this.#disposed) {
                return;
            }
            this.#handleError(ensureError(error), 'File Explorer mkdir failed');
        }
    }

    async createFile(path: string, content: string): Promise<void> {
        try {
            this.#requireActive();
            const destination = toVirtualPath(path);
            const uploadSession = this.#recentUploads.beginUploadSession();
            await this.#host.api.write(destination, content);
            if (this.#disposed) {
                return;
            }
            const fileMarked = this.#recentUploads.markCreatedPath(uploadSession, destination);
            await this.#refreshRetainingMarks(uploadSession, fileMarked);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#disposed) {
                return;
            }
            this.#handleError(runtimeError, 'File Explorer create file failed');
            throw runtimeError;
        }
    }

    async writeFile(path: string, content: string): Promise<void> {
        try {
            this.#requireActive();
            const normalized = toVirtualPath(path);
            await this.#host.api.write(normalized, content);
            if (this.#disposed) {
                return;
            }
            await this.#refresh();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#disposed) {
                return;
            }
            this.#handleError(runtimeError, 'File Explorer write failed');
            throw runtimeError;
        }
    }

    async movePath(sourcePath: string, destinationPath: string): Promise<void> {
        const source = toVirtualPath(sourcePath);
        const destination = toVirtualPath(destinationPath);
        if (source === destination) {
            throw new Error('File Explorer move requires different source and destination paths');
        }
        await this.#commitMove(source, destination, false);
    }

    async renamePath(sourcePath: string, newLeafName: string): Promise<void> {
        const source = toVirtualPath(sourcePath);
        const currentLeaf = filenameFromPath(source);
        if (validateFileExplorerRenameLeaf(newLeafName, currentLeaf) !== null) {
            throw new Error('File Explorer rename requires a valid new leaf name');
        }
        const destination = joinVirtualPath(parentVirtualPath(source), normalizeFileExplorerRenameLeaf(newLeafName));
        if (source === destination) {
            throw new Error('File Explorer rename requires a different destination path');
        }
        await this.#commitMove(source, destination, true);
    }

    async #commitMove(source: string, destination: string, renamed: boolean): Promise<void> {
        const capturedSelection = this.#selectionModel.captureSelection([source]);
        try {
            this.#requireActive();
            await this.#host.api.move(source, destination);
            if (this.#disposed) {
                return;
            }
            this.#selectionModel.replaceRenamedPath(capturedSelection, source, destination);
            if (renamed) this.#host.showNotification(i18n.t('fileExplorer.notifications.renameSuccess', { path: destination }), 'success');
            await this.#refresh();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#disposed) {
                return;
            }
            this.#handleError(runtimeError, renamed ? 'File Explorer rename failed' : 'File Explorer move failed');
            throw runtimeError;
        }
    }

    async deletePath(path: string, onCommitted: () => void): Promise<FileExplorerDeletionOutcome> {
        const normalizedPath = toVirtualPath(path);
        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('fileExplorer.confirmations.deleteTitle'),
            message: i18n.t('fileExplorer.confirmations.deleteMessage', { path: normalizedPath }),
            confirmText: i18n.t('fileExplorer.confirmations.confirmDelete'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        });
        if (!confirmed) {
            return 'cancelled';
        }
        try {
            this.#requireActive();
            await this.#host.api.delete(normalizedPath);
        } catch (error) {
            if (this.#disposed || isAbortError(error)) return 'cancelled';
            this.#operationFailures.report(ensureError(error), { context: 'File Explorer delete failed', notificationMessage: i18n.t('fileExplorer.status.error'), statusMessages: FILE_EXPLORER_HTTP_STATUS_MESSAGES });
            return 'failed';
        }
        if (this.#disposed) return 'committed';
        onCommitted();
        this.#host.showNotification(i18n.t('fileExplorer.notifications.deleteSuccess', { path: normalizedPath }), 'success');
        await this.#refresh();
        return 'committed';
    }

    async downloadPath(path: string, options: { signal?: AbortSignal } = {}): Promise<void> {
        try {
            this.#requireActive();
            const normalizedPath = toVirtualPath(path);
            const responseValue = await this.#host.api.download(normalizedPath, options);
            if (this.#disposed) {
                return;
            }
            const filename = filenameFromPath(path);
            await downloadAuthenticatedResponse(responseValue, { filename });
            if (this.#disposed) {
                return;
            }
            this.#host.showNotification(i18n.t('fileExplorer.notifications.downloadSuccess', { path: normalizedPath }), 'download');
        } catch (error) {
            if (this.#disposed) {
                return;
            }
            this.#handleError(ensureError(error), 'File Explorer download failed');
        }
    }

    async downloadSelection(paths: readonly string[], options: { signal?: AbortSignal } = {}): Promise<void> {
        try {
            this.#requireActive();
            if (paths.length < 2) {
                throw new Error('File Explorer selection download requires at least two paths');
            }
            const normalizedPaths = paths.map((path) => toVirtualPath(path));
            const responseValue = await this.#host.api.downloadSelection(normalizedPaths, options);
            if (this.#disposed) return;
            await downloadAuthenticatedResponse(responseValue, { filename: 'file-explorer-selection.zip' });
            if (this.#disposed) return;
            this.#host.showNotification(i18n.t('fileExplorer.notifications.downloadSelectionSuccess', { count: normalizedPaths.length }), 'download');
        } catch (error) {
            if (this.#disposed) return;
            this.#handleError(ensureError(error), 'File Explorer selection download failed');
        }
    }

    async #refreshRetainingMarks(uploadSession: FileExplorerUploadMarkerSession, marked: boolean): Promise<void> {
        if (!this.#recentUploads.isUploadSessionCurrent(uploadSession)) {
            return;
        }
        if (marked) {
            this.#recentUploads.retainAcrossNextLoad();
        }
        await this.#refresh(marked ? uploadSession : undefined);
    }

    async #refresh(uploadSession?: FileExplorerUploadMarkerSession): Promise<void> {
        if (this.#disposed) return;
        try {
            await this.#selection.refresh(uploadSession);
        } catch (error) {
            if (this.#disposed || isAbortError(error)) return;
            errorHandler.warn('FileExplorer', 'File mutation committed before the view refresh failed', ensureError(error));
            this.#host.showNotification(i18n.t('fileExplorer.errors.changeRefreshFailed'), 'warning');
        }
    }

    #handleError(error: Error, context: string): void {
        if (notifyFileExplorerHttpError(this.#host, error)) {
            return;
        }
        this.#host.handleError(error, context, { notify: true });
    }

    #requireActive(): void {
        if (this.#disposed) {
            throw new Error('File Explorer operations controller is disposed');
        }
    }
}

export { FileExplorerOperationsController };
export type { FileExplorerDeletionOutcome };
