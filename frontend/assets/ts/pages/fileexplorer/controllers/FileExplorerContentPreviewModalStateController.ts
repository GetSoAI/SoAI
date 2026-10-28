/* SoAI - File explorer page control layer content preview modal state controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerContentPreviewModalStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { joinVirtualPath, parentVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { resolveFileExplorerPreviewHeaderDescription } from '@core/ui/modals/contentpreview/headerDescriptions.ts';
import type { FileBrowserMetadata } from '@core/fileexplorerbrowser/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { resolveFileEntryTypeLabel } from '@core/fileexplorerbrowser/entryTypeLabels.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { ContentPreviewTextDraftSnapshot, ContentPreviewTextSaveResult } from '@core/ui/modals/contentpreview/types.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { filenameFromPath } from '@pages/fileexplorer/controllers/fileExplorerOperations.ts';
import { downloadFileExplorerContentPreviewPath } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewTransferController.ts';
import { FileExplorerContentPreviewValidationController } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewValidationController.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { commitExistingFileTextSaveTransaction } from '@core/fileexplorerbrowser/fileTextSaveTransaction.ts';

interface FileExplorerContentPreviewModalStateHost {
    showNotification(message: string, type: NotificationType): void;
    writeFile(path: string, content: string): Promise<void>;
    createFile(path: string, content: string): Promise<void>;
    movePath(sourcePath: string, destinationPath: string): Promise<void>;
    downloadPath(path: string): Promise<void>;
    loadMetadata(path: string): Promise<FileBrowserMetadata>;
}

const buildCommittedTextSaveResult = (path: string, content: string, headerDescription: string): ContentPreviewTextSaveResult =>
    Object.freeze({
        baseline: Object.freeze({
            title: filenameFromPath(path),
            content,
            promptColor: null
        }),
        sourceReference: Object.freeze({ type: 'path', value: path }),
        headerDescription
    });

class FileExplorerContentPreviewModalStateController {
    readonly #host: FileExplorerContentPreviewModalStateHost;
    #path: string | null = null;
    #baselineContent: string | null = null;
    #isNewFile = false;
    #stateRevision = 0;
    #saveInProgress = false;

    constructor(host: FileExplorerContentPreviewModalStateHost) {
        this.#host = host;
    }

    setTextBaseline(path: string, content: string, options: { isNewFile: boolean }): void {
        this.#stateRevision += 1;
        this.#path = path;
        this.#baselineContent = content;
        this.#isNewFile = options.isNewFile;
    }

    clear(): void {
        this.#stateRevision += 1;
        this.#path = null;
        this.#baselineContent = null;
        this.#isNewFile = false;
    }

    invalidatePendingSaveResult(): void {
        this.#stateRevision += 1;
    }

    getPath(): string | null {
        return this.#path;
    }

    hasUnsavedChanges(): boolean {
        const service = requireContentPreviewModalService();
        return FileExplorerContentPreviewValidationController.hasUnsavedChanges({
            path: this.#path,
            baselineContent: this.#baselineContent,
            isNewFile: this.#isNewFile,
            isEditing: () => service.isEditing(),
            getDraftSnapshot: () => service.getTextDraftSnapshot()
        });
    }

    isPendingEditValid(): boolean {
        const service = requireContentPreviewModalService();
        return FileExplorerContentPreviewValidationController.isPendingEditValid({
            isEditing: () => service.isEditing(),
            getDraftSnapshot: () => service.getTextDraftSnapshot()
        });
    }

    async applySave(draft: ContentPreviewTextDraftSnapshot): Promise<ContentPreviewTextSaveResult | null> {
        const path = this.#path;
        if (!path) {
            throw new Error('File content preview modal cannot save before a file is opened');
        }
        if (this.#saveInProgress) {
            return null;
        }
        this.#saveInProgress = true;
        const stateRevision = this.#stateRevision;
        const isNewFile = this.#isNewFile;
        const normalizedTitle = draft.title.trim();
        const requestedFilename = normalizedTitle ? filenameFromPath(normalizedTitle) : '';
        const requestedPath = requestedFilename ? joinVirtualPath(parentVirtualPath(path), requestedFilename) : path;
        const content = draft.content;

        try {
            let committedPath = requestedPath;
            if (isNewFile) {
                await this.#host.createFile(requestedPath, content);
            } else {
                const outcome = await commitExistingFileTextSaveTransaction({
                    sourcePath: path,
                    destinationPath: requestedPath,
                    content,
                    writeFile: (writePath, writeContent) => this.#host.writeFile(writePath, writeContent),
                    movePath: (sourcePath, destinationPath) => this.#host.movePath(sourcePath, destinationPath)
                });
                committedPath = outcome.committedPath;
                if (outcome.renameError) {
                    if (this.#stateRevision !== stateRevision) {
                        return null;
                    }
                    this.#path = path;
                    this.#baselineContent = content;
                    this.#isNewFile = false;
                    this.#host.showNotification(i18n.t('fileExplorer.modal.saveRenameFailed'), 'warning');
                    return await this.#committedResult(path, content, stateRevision);
                }
            }
            if (this.#stateRevision !== stateRevision) {
                return null;
            }
            this.#path = committedPath;
            this.#baselineContent = content;
            this.#isNewFile = false;
            this.#host.showNotification(i18n.t('fileExplorer.modal.saveSuccess'), 'success');
            return await this.#committedResult(committedPath, content, stateRevision);
        } finally {
            this.#saveInProgress = false;
        }
    }

    async #committedResult(path: string, content: string, stateRevision: number): Promise<ContentPreviewTextSaveResult | null> {
        let headerDescription = resolveFileEntryTypeLabel('text');
        try {
            const metadata = await this.#host.loadMetadata(path);
            headerDescription = resolveFileExplorerPreviewHeaderDescription(metadata);
        } catch (error) {
            if (this.#stateRevision !== stateRevision || isAbortError(error)) return null;
            errorHandler.warn('FileExplorerContentPreview', 'File content committed before its metadata refresh failed', ensureError(error));
            this.#host.showNotification(i18n.t('fileExplorer.errors.changeRefreshFailed'), 'warning');
        }
        if (this.#stateRevision !== stateRevision) return null;
        return buildCommittedTextSaveResult(path, content, headerDescription);
    }

    async downloadCurrent(): Promise<void> {
        const path = this.#path;
        if (!path) {
            throw new Error('File content preview modal cannot download before a file is opened');
        }
        await downloadFileExplorerContentPreviewPath(this.#host, path);
    }
}

export { FileExplorerContentPreviewModalStateController };
export type { FileExplorerContentPreviewModalStateHost };
