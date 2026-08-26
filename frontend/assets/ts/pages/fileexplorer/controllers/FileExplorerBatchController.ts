/* SoAI - File Explorer batch task controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerBatchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { notifyFileExplorerHttpError } from '@pages/fileexplorer/controllers/fileExplorerHttpErrorController.ts';
import type { FileExplorerControllerHost, FileExplorerSelectionProvider } from '@pages/fileexplorer/types.ts';

class FileExplorerBatchController {
    #host: FileExplorerControllerHost;
    #selection: FileExplorerSelectionProvider;
    #disposed = false;

    constructor(dependencies: { host: FileExplorerControllerHost; selection: FileExplorerSelectionProvider }) {
        this.#host = dependencies.host;
        this.#selection = dependencies.selection;
    }

    destroy(): void {
        this.#disposed = true;
    }

    async batchDeleteTask(paths: readonly string[]): Promise<string | null> {
        try {
            this.#requireActive();
            const normalized = paths.map((path) => toVirtualPath(path));
            if (normalized.length <= 0) {
                this.#host.showNotification(i18n.t('fileExplorer.errors.selectionRequired'), 'error');
                return null;
            }
            const confirmed = await requireDialogsService().showConfirmation({
                title: i18n.t('fileExplorer.confirmations.batchDeleteTitle'),
                message: i18n.t('fileExplorer.confirmations.batchDeleteMessage', { count: normalized.length }),
                confirmText: i18n.t('fileExplorer.confirmations.confirmDelete'),
                cancelText: i18n.t('common.cancel'),
                variant: 'danger'
            });
            if (!confirmed) return null;
            this.#requireActive();
            const payload = await this.#host.api.batchDeleteTask(normalized);
            if (this.#disposed) return null;
            const taskId = payload.taskId;
            this.#host.showNotification(i18n.t('fileExplorer.notifications.taskStarted', { taskId: taskId }), 'info');
            this.#refreshSelection();
            return taskId;
        } catch (error) {
            if (this.#disposed) return null;
            const runtimeError = ensureError(error);
            this.#handleError(runtimeError, 'File Explorer batch delete failed');
            throw runtimeError;
        }
    }

    async batchCopyTask(paths: readonly string[], destinationDir: string): Promise<string | null> {
        try {
            this.#requireActive();
            const normalized = paths.map((path) => toVirtualPath(path));
            if (normalized.length <= 0) {
                this.#host.showNotification(i18n.t('fileExplorer.errors.selectionRequired'), 'error');
                return null;
            }
            const destination = toVirtualPath(destinationDir);
            const payload = await this.#host.api.batchCopyTask(normalized, destination);
            if (this.#disposed) return null;
            const taskId = payload.taskId;
            this.#host.showNotification(i18n.t('fileExplorer.notifications.taskStarted', { taskId: taskId }), 'copy');
            this.#refreshSelection();
            return taskId;
        } catch (error) {
            if (this.#disposed) return null;
            const runtimeError = ensureError(error);
            this.#handleError(runtimeError, 'File Explorer batch copy failed');
            throw runtimeError;
        }
    }

    async batchMoveTask(paths: readonly string[], destinationDir: string): Promise<string | null> {
        try {
            this.#requireActive();
            const normalized = paths.map((path) => toVirtualPath(path));
            if (normalized.length <= 0) {
                this.#host.showNotification(i18n.t('fileExplorer.errors.selectionRequired'), 'error');
                return null;
            }
            const destination = toVirtualPath(destinationDir);
            const confirmed = await requireDialogsService().showConfirmation({
                title: i18n.t('fileExplorer.confirmations.batchMoveTitle'),
                message: i18n.t('fileExplorer.confirmations.batchMoveMessage', {
                    count: normalized.length,
                    destination
                }),
                confirmText: i18n.t('fileExplorer.confirmations.confirmMove'),
                cancelText: i18n.t('common.cancel'),
                variant: 'warning'
            });
            if (!confirmed) return null;
            this.#requireActive();
            const payload = await this.#host.api.batchMoveTask(normalized, destination);
            if (this.#disposed) return null;
            const taskId = payload.taskId;
            this.#host.showNotification(i18n.t('fileExplorer.notifications.taskStarted', { taskId: taskId }), 'info');
            this.#refreshSelection();
            return taskId;
        } catch (error) {
            if (this.#disposed) return null;
            const runtimeError = ensureError(error);
            this.#handleError(runtimeError, 'File Explorer batch move failed');
            throw runtimeError;
        }
    }

    #refreshSelection(): void {
        if (this.#disposed) return;
        void this.#selection.refresh().catch((error) => {
            if (this.#disposed) return;
            this.#host.handleError(ensureError(error), 'File Explorer refresh after task start failed', { notify: false });
        });
    }

    #handleError(error: Error, context: string): void {
        if (notifyFileExplorerHttpError(this.#host, error)) {
            return;
        }
        this.#host.handleError(error, context, { notify: true });
    }

    #requireActive(): void {
        if (this.#disposed) {
            throw new Error('File Explorer batch controller is disposed');
        }
    }
}

export { FileExplorerBatchController };
