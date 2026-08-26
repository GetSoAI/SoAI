/* SoAI - File explorer page control layer content preview modal controller [frontend/assets/ts/pages/fileexplorer/controllers/FileExplorerContentPreviewModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFileBrowserAudioPreviewMimeType, isFileBrowserImagePreviewMimeType, isFileBrowserTextPreviewMimeType, isFileBrowserVideoPreviewMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import type { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import type { FileBrowserMetadata } from '@core/fileexplorerbrowser/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { CONTENT_PREVIEW_MODAL_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { createDocumentContentPreviewRequest, createMediaContentPreviewRequest, createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import { resolveFileExplorerPreviewHeaderDescription } from '@core/ui/modals/contentpreview/headerDescriptions.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { ContentPreviewImageNavigationDirection, ContentPreviewTextBaseline, ContentPreviewTextDraftSnapshot, ContentPreviewTextSaveResult } from '@core/ui/modals/contentpreview/types.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { filenameFromPath } from '@pages/fileexplorer/controllers/fileExplorerOperations.ts';
import { createFileExplorerContentPreviewMedia, revokeFileExplorerContentPreviewMediaUrl, type FileExplorerContentPreviewMediaType } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewMediaController.ts';
import { copyFileExplorerContentPreviewSoaiLink, copyFileExplorerContentPreviewText } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewTransferController.ts';
import { FileExplorerContentPreviewImageNavigationController } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewImageNavigationController.ts';
import { FileExplorerContentPreviewModalStateController } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewModalStateController.ts';
import { FileExplorerContentPreviewObjectUrlController } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewObjectUrlController.ts';
import { FileExplorerContentPreviewRequestController } from '@pages/fileexplorer/controllers/FileExplorerContentPreviewRequestController.ts';

interface FileExplorerContentPreviewModalHost {
    requireHTMLElement(selector: string, context?: HTMLElement): HTMLElement;
    modalPresenter: ModalPresenterApi;
    showNotification(message: string, type: NotificationType): void;
    readPath(path: string): Promise<{ path: string; content: string }>;
    loadMetadata(path: string): Promise<FileBrowserMetadata>;
    downloadResponse(path: string): Promise<BufferedApiResponse>;
    downloadPath(path: string): Promise<void>;
    writeFile(path: string, content: string): Promise<void>;
    createFile(path: string, content: string): Promise<void>;
    movePath(sourcePath: string, destinationPath: string): Promise<void>;
    getCurrentFolderImagePaths(): readonly string[];
    runWithBoundary(operation: string, task: () => Promise<void>): Promise<void>;
}

class FileExplorerContentPreviewModalController {
    readonly #host: FileExplorerContentPreviewModalHost;
    readonly #save: SaveController;
    readonly #resources = new ResourceTracker();
    readonly #state: FileExplorerContentPreviewModalStateController;
    readonly #imageNavigation: FileExplorerContentPreviewImageNavigationController;
    readonly #objectUrl = new FileExplorerContentPreviewObjectUrlController();
    readonly #previewRequest = new FileExplorerContentPreviewRequestController();
    #wired = false;

    constructor(host: FileExplorerContentPreviewModalHost) {
        this.#host = host;
        this.#state = new FileExplorerContentPreviewModalStateController(host);
        this.#imageNavigation = new FileExplorerContentPreviewImageNavigationController({
            getCurrentFolderImagePaths: () => this.#host.getCurrentFolderImagePaths(),
            getCurrentPath: () => this.#previewRequest.currentPath(),
            openPath: async (path: string, direction: ContentPreviewImageNavigationDirection): Promise<void> => {
                await this.#host.runWithBoundary('fileExplorer:contentPreview:imageNavigation', async () => {
                    await this.#show(path, direction);
                });
            }
        });
        this.#save = createSaveController({
            headerContextId: CONTENT_PREVIEW_MODAL_ID,
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'File Explorer save',
            units: [
                {
                    id: 'fileExplorer.contentPreviewModal',
                    hasChanges: () => this.#state.hasUnsavedChanges(),
                    isValid: () => this.#state.isPendingEditValid(),
                    save: async () => {
                        await requireContentPreviewModalService().requestSave();
                    }
                }
            ]
        });
    }

    async show(path: string): Promise<void> {
        await this.#show(path, null);
    }

    async #show(path: string, imageNavigationDirection: ContentPreviewImageNavigationDirection | null): Promise<void> {
        const normalized = this.#previewRequest.normalizePath(path, 'File content preview modal requires a file path');
        const sequence = this.#previewRequest.begin(normalized);
        try {
            const metadata = await this.#host.loadMetadata(normalized);
            if (!this.#previewRequest.isCurrent(sequence)) {
                return;
            }
            if (metadata.isDirectory) {
                throw new Error('File content preview modal requires a file path');
            }
            const headerDescription = resolveFileExplorerPreviewHeaderDescription(metadata);
            if (isFileBrowserImagePreviewMimeType(metadata.mimeType)) {
                await this.#showMedia(normalized, 'image', sequence, headerDescription, imageNavigationDirection);
                return;
            }
            if (isFileBrowserAudioPreviewMimeType(metadata.mimeType)) {
                await this.#showMedia(normalized, 'audio', sequence, headerDescription, null);
                return;
            }
            if (isFileBrowserVideoPreviewMimeType(metadata.mimeType)) {
                await this.#showMedia(normalized, 'video', sequence, headerDescription, null);
                return;
            }
            if (!isFileBrowserTextPreviewMimeType(metadata.mimeType)) {
                this.#showDocument(normalized, sequence, headerDescription);
                return;
            }
            const result = await this.#host.readPath(normalized);
            if (!this.#previewRequest.isCurrent(sequence)) {
                return;
            }
            this.#openTextPreview(result.path, result.content, headerDescription, metadata.mimeType, true, false);
            this.#state.setTextBaseline(result.path, result.content, { isNewFile: false });
            const modalRoot = this.#host.modalPresenter.requireElement(CONTENT_PREVIEW_MODAL_ID);
            this.#ensureWired(modalRoot);
            this.#attachSave(modalRoot);
            this.#objectUrl.replace(null);
        } catch (error) {
            if (this.#previewRequest.isCurrent(sequence)) {
                const runtimeError = ensureError(error);
                this.#previewRequest.setCurrentPath(this.#state.getPath());
                throw runtimeError;
            }
        }
    }

    #showDocument(path: string, sequence: number, headerDescription: string): void {
        if (!this.#previewRequest.isCurrent(sequence)) {
            return;
        }
        const normalized = this.#previewRequest.normalizePath(path, 'File content preview modal requires a file path');

        requireContentPreviewModalService().open(
            createDocumentContentPreviewRequest({
                scope: 'fileExplorer',
                type: 'document',
                headerDescription,
                title: filenameFromPath(normalized),
                sourceReference: { type: 'path', value: normalized },
                onRequestDownload: async (): Promise<void> => await this.#state.downloadCurrent(),
                onRequestAttach: async (): Promise<void> => await copyFileExplorerContentPreviewSoaiLink(this.#host, this.#state.getPath()),
                openSourceUrl: null
            })
        );

        this.#state.setTextBaseline(normalized, '', { isNewFile: false });
        const modalRoot = this.#host.modalPresenter.requireElement(CONTENT_PREVIEW_MODAL_ID);
        this.#ensureWired(modalRoot);
        this.#save.attach({ resolveSaveButtons: () => [], enableHeaderAction: false, autoNotifyRoot: modalRoot });
        this.#objectUrl.replace(null);
    }

    async #showMedia(path: string, type: FileExplorerContentPreviewMediaType, sequence: number, headerDescription: string, imageNavigationDirection: ContentPreviewImageNavigationDirection | null): Promise<void> {
        const previewMedia = await createFileExplorerContentPreviewMedia(this.#host, path);
        if (!this.#previewRequest.isCurrent(sequence)) {
            revokeFileExplorerContentPreviewMediaUrl(previewMedia.sourceUrl);
            return;
        }
        try {
            const request = createMediaContentPreviewRequest({
                scope: 'fileExplorer',
                type,
                headerDescription,
                title: filenameFromPath(path),
                sourceUrl: previewMedia.sourceUrl,
                imageMetadata: previewMedia.imageMetadata,
                imageNavigation: type === 'image' ? this.#imageNavigation.createNavigation() : null,
                sourceReference: { type: 'path', value: path },
                onRequestDownload: async (): Promise<void> => await this.#state.downloadCurrent(),
                onRequestAttach: async (): Promise<void> => await copyFileExplorerContentPreviewSoaiLink(this.#host, this.#state.getPath()),
                openSourceUrl: null
            });
            const service = requireContentPreviewModalService();
            if (imageNavigationDirection === null) {
                service.open(request);
            } else {
                const committed = await service.completeImageNavigation(request, imageNavigationDirection);
                if (!committed) {
                    revokeFileExplorerContentPreviewMediaUrl(previewMedia.sourceUrl);
                    return;
                }
            }
            this.#objectUrl.replace(previewMedia.sourceUrl);
            this.#state.setTextBaseline(path, '', { isNewFile: false });
            const modalRoot = this.#host.modalPresenter.requireElement(CONTENT_PREVIEW_MODAL_ID);
            this.#ensureWired(modalRoot);
            this.#save.attach({ resolveSaveButtons: () => [], enableHeaderAction: false, autoNotifyRoot: modalRoot });
        } catch (error) {
            if (this.#objectUrl.current() !== previewMedia.sourceUrl) {
                revokeFileExplorerContentPreviewMediaUrl(previewMedia.sourceUrl);
            }
            throw ensureError(error);
        }
    }

    showNewFile(path: string): void {
        const normalized = this.#previewRequest.normalizePath(path, 'New file path is required');
        this.#previewRequest.begin(normalized);
        const service = requireContentPreviewModalService();
        this.#openTextPreview(normalized, '', null, '', false, true);
        this.#state.setTextBaseline(normalized, '', { isNewFile: true });
        const modalRoot = this.#host.modalPresenter.requireElement(CONTENT_PREVIEW_MODAL_ID);
        this.#ensureWired(modalRoot);
        this.#attachSave(modalRoot);
        this.#objectUrl.replace(null);
        service.enterEditMode();
    }

    #openTextPreview(path: string, content: string, headerDescription: string | null, mimeType: string, allowAttach: boolean, isUnsavedDraft: boolean): void {
        const baseline: ContentPreviewTextBaseline = Object.freeze({
            title: filenameFromPath(path),
            content,
            promptColor: null
        });
        requireContentPreviewModalService().open(
            createTextContentPreviewRequest({
                scope: 'fileExplorer',
                type: 'text',
                headerDescription,
                baseline,
                editable: true,
                isUnsavedDraft,
                languageMode: 'default',
                disableCopyWhenEmpty: false,
                disableDownloadWhenEmpty: false,
                colorToolkit: null,
                sourceReference: { type: 'path', value: path },
                onRequestSave: async (draft: ContentPreviewTextDraftSnapshot): Promise<ContentPreviewTextSaveResult | null> => await this.#applyTextSave(draft, mimeType),
                onRequestDownload: async (): Promise<void> => await this.#state.downloadCurrent(),
                onRequestCopy: async (text: string): Promise<void> => await copyFileExplorerContentPreviewText(this.#host, text),
                onRequestAttach: allowAttach ? async (): Promise<void> => await copyFileExplorerContentPreviewSoaiLink(this.#host, this.#state.getPath()) : null,
                enhance: null,
                openSourceUrl: null,
                onStatePotentiallyChanged: () => this.#save.notifyChanged()
            })
        );
    }

    dispose(): void {
        this.#previewRequest.clear();
        this.#objectUrl.revoke();
        this.#resources.cleanup();
        this.#save.dispose();
        this.#state.clear();
        this.#wired = false;
    }

    #ensureWired(modalRoot: HTMLElement): void {
        if (this.#wired) {
            return;
        }
        this.#resources.addEventListener(modalRoot, 'core.modal.close', () => this.#onModalClose());
        this.#wired = true;
    }

    #onModalClose(): void {
        this.#previewRequest.clear();
        this.#objectUrl.revoke();
        this.#state.clear();
        this.#save.attach({ resolveSaveButtons: () => [], enableHeaderAction: false, autoNotifyRoot: null });
    }

    #attachSave(modalRoot: HTMLElement): void {
        setAriaBusy(modalRoot, false);
        this.#save.attach({
            resolveSaveButtons: () => {
                if (!requireContentPreviewModalService().isEditing()) {
                    return [];
                }
                const candidate = this.#host.requireHTMLElement(modalUiSelector(CONTENT_PREVIEW_MODAL_ID, 'save'), modalRoot);
                return candidate instanceof HTMLButtonElement ? [candidate] : [];
            },
            busyRoots: [modalRoot],
            autoNotifyRoot: modalRoot
        });
    }

    async #applyTextSave(draft: ContentPreviewTextDraftSnapshot, mimeType: string): Promise<ContentPreviewTextSaveResult | null> {
        const result = await this.#state.applySave(draft, mimeType);
        if (result?.sourceReference?.type === 'path') {
            this.#previewRequest.setCurrentPath(result.sourceReference.value);
        }
        return result;
    }
}

export { FileExplorerContentPreviewModalController };
export type { FileExplorerContentPreviewModalHost };
