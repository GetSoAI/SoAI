/* SoAI - File Explorer single-path operations controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerOperationsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerBatchUploadResponse, FileExplorerUploadResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { joinVirtualPath, parentVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { notifyFileExplorerHttpError } from '@pages/fileexplorer/controllers/fileExplorerHttpErrorController.ts';
import { filenameFromPath, normalizeFileExplorerRenameLeaf, toFiles, validateFileExplorerRenameLeaf } from '@pages/fileexplorer/controllers/fileExplorerOperations.ts';
import type { FileExplorerRecentUploadController } from '@pages/fileexplorer/controllers/FileExplorerRecentUploadController.ts';
import type { FileExplorerControllerHost, FileExplorerSelectionProvider, FileExplorerUploadMarkerSession, FileExplorerUploadUi } from '@pages/fileexplorer/types.ts';

class FileExplorerOperationsController {
    #host: FileExplorerControllerHost;
    #ui: FileExplorerUploadUi;
    #selection: FileExplorerSelectionProvider;
    #recentUploads: FileExplorerRecentUploadController;
    #disposed = false;

    constructor(dependencies: { host: FileExplorerControllerHost; ui: FileExplorerUploadUi; selection: FileExplorerSelectionProvider; recentUploads: FileExplorerRecentUploadController }) {
        this.#host = dependencies.host;
        this.#ui = dependencies.ui;
        this.#selection = dependencies.selection;
        this.#recentUploads = dependencies.recentUploads;
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
                if (response.succeeded > 0) {
                    this.#host.showNotification(i18n.t('fileExplorer.notifications.uploadPartial', { succeeded: response.succeeded, failed: response.failed }), 'warning');
                } else {
                    this.#host.showNotification(i18n.t('fileExplorer.notifications.uploadFailed', { succeeded: response.succeeded, failed: response.failed }), 'error');
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
        try {
            this.#requireActive();
            await this.#host.api.move(source, destination);
            if (this.#disposed) {
                return;
            }
            await this.#refresh();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#disposed) {
                return;
            }
            this.#handleError(runtimeError, 'File Explorer move failed');
            throw runtimeError;
        }
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
        try {
            this.#requireActive();
            await this.#host.api.move(source, destination);
            if (this.#disposed) {
                return;
            }
            this.#host.showNotification(i18n.t('fileExplorer.notifications.renameSuccess', { path: destination }), 'success');
            await this.#refresh();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#disposed) {
                return;
            }
            this.#handleError(runtimeError, 'File Explorer rename failed');
            throw runtimeError;
        }
    }

    async deletePath(path: string): Promise<void> {
        const normalizedPath = toVirtualPath(path);
        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('fileExplorer.confirmations.deleteTitle'),
            message: i18n.t('fileExplorer.confirmations.deleteMessage', { path: normalizedPath }),
            confirmText: i18n.t('fileExplorer.confirmations.confirmDelete'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        });
        if (!confirmed) {
            return;
        }
        try {
            this.#requireActive();
            await this.#host.api.delete(normalizedPath);
            if (this.#disposed) {
                return;
            }
            this.#host.showNotification(i18n.t('fileExplorer.notifications.deleteSuccess', { path: normalizedPath }), 'success');
            await this.#refresh();
        } catch (error) {
            if (this.#disposed) {
                return;
            }
            this.#handleError(ensureError(error), 'File Explorer delete failed');
        }
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
        await this.#selection.refresh(marked ? uploadSession : undefined);
    }

    async #refresh(): Promise<void> {
        this.#requireActive();
        await this.#selection.refresh();
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
