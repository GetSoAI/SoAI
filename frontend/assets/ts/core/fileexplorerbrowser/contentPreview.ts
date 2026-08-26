/* SoAI - File explorer content preview modal launcher [frontend/assets/ts/core/fileexplorerbrowser/contentPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import type { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import type { FileExplorerMetadataResponse, FileExplorerMoveMutationResponse, FileExplorerPathMutationResponse, FileExplorerReadResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { buildFileExplorerPreviewUrl } from '@core/api/endpoints/fileExplorerPaths.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { buildFileExplorerDeepLink } from '@core/fileexplorerbrowser/deepLinks.ts';
import { classifyFileBrowserMimeType } from '@core/fileexplorerbrowser/mediaClassification.ts';
import { parseFileBrowserMetadataPayload, parseFileBrowserReadPayload } from '@core/fileexplorerbrowser/payloads.ts';
import { basenameVirtualPath, joinVirtualPath, parentVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { copySoaiPathLinkToClipboard } from '@core/fileexplorerbrowser/soaiPathClipboard.ts';
import type { FileBrowserMetadata } from '@core/fileexplorerbrowser/types.ts';
import { requirePathLeaf } from '@core/filePathResolution.ts';
import { i18n } from '@core/i18n/index.ts';
import { hasFunctionProperties, isObject } from '@core/typeGuards.ts';
import { createDocumentContentPreviewRequest, createMediaContentPreviewRequest, createTextContentPreviewRequest } from '@core/ui/modals/contentpreview/requestFactories.ts';
import { resolveFileExplorerPreviewHeaderDescription, resolveFileExplorerPreviewHeaderDescriptionForFile } from '@core/ui/modals/contentpreview/headerDescriptions.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { ContentPreviewSourceReference, ContentPreviewTextDraftSnapshot, ContentPreviewTextSaveResult } from '@core/ui/modals/contentpreview/types.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { copyTextWithBrowserClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { commitExistingFileTextSaveTransaction } from '@core/fileexplorerbrowser/fileTextSaveTransaction.ts';
import { errorHandler } from '@core/errorHandler.ts';

interface FileExplorerContentPreviewApi {
    fileExplorer: {
        metadata(path: string, options?: { includeHash?: boolean }): Promise<FileExplorerMetadataResponse>;
        read(path: string): Promise<FileExplorerReadResponse>;
        download(path: string): Promise<BufferedApiResponse>;
        write(path: string, content: string): Promise<FileExplorerPathMutationResponse>;
        move(source: string, destination: string): Promise<FileExplorerMoveMutationResponse>;
    };
}

let fileExplorerPreviewSequence = 0;

const isCurrentFileExplorerPreviewRequest = (sequence: number): boolean => sequence === fileExplorerPreviewSequence;

const cancelFileExplorerContentPreviewRequest = (): void => {
    fileExplorerPreviewSequence += 1;
};

const isFileExplorerContentPreviewApi = <T>(value: T): value is T & FileExplorerContentPreviewApi => {
    if (!isObject(value)) {
        return false;
    }
    if (!('fileExplorer' in value)) {
        return false;
    }
    const fileExplorer = value['fileExplorer'];
    if (!isObject(fileExplorer)) {
        return false;
    }
    return hasFunctionProperties(fileExplorer, ['metadata', 'read', 'download', 'write', 'move']);
};

const downloadFileExplorerPreviewPath = async (api: FileExplorerContentPreviewApi, path: string): Promise<void> => {
    const responseValue = await api.fileExplorer.download(path);
    await downloadAuthenticatedResponse(responseValue, { filename: basenameVirtualPath(path) });
};

const copyFileExplorerPreviewText = async (text: string): Promise<void> => {
    await copyTextWithBrowserClipboardFeedback(
        {
            showNotification: (message, type): void => {
                showNotification(message, type);
            }
        },
        {
            text,
            successMessage: i18n.t('fileExplorer.modal.copySuccess'),
            errorMessage: i18n.t('fileExplorer.modal.copyFailed'),
            unavailableMessage: i18n.t('fileExplorer.modal.copyFailed'),
            unavailableType: 'error'
        }
    );
};

const buildFileExplorerSourceUrl = (path: string): string => {
    const normalized = toVirtualPath(path);
    return buildFileExplorerDeepLink({
        directoryPath: parentVirtualPath(normalized),
        highlightPath: normalized,
        search: basenameVirtualPath(normalized)
    });
};

const createSourceReference = (metadata: FileBrowserMetadata): ContentPreviewSourceReference => ({ type: 'path', value: metadata.path });

const saveFileExplorerPreviewText = async (api: FileExplorerContentPreviewApi, path: string, mimeType: string, draft: ContentPreviewTextDraftSnapshot, isCurrent: () => boolean): Promise<ContentPreviewTextSaveResult | null> => {
    const requestedFilename = requirePathLeaf(draft.title, 'File preview title filename is required');
    const requestedPath = joinVirtualPath(parentVirtualPath(path), requestedFilename);
    const outcome = await commitExistingFileTextSaveTransaction({
        sourcePath: path,
        destinationPath: requestedPath,
        content: draft.content,
        writeFile: (writePath, content) => api.fileExplorer.write(writePath, content).then(() => undefined),
        movePath: (sourcePath, destinationPath) => api.fileExplorer.move(sourcePath, destinationPath).then(() => undefined)
    });
    if (!isCurrent()) {
        return null;
    }
    if (outcome.renameError) {
        errorHandler.warn('FileExplorerContentPreview', 'File content committed before rename failed', {
            sourcePath: path,
            destinationPath: requestedPath,
            error: outcome.renameError
        });
        showNotification(i18n.t('fileExplorer.modal.saveRenameFailed'), 'warning');
    } else {
        showNotification(i18n.t('fileExplorer.modal.saveSuccess'), 'success');
    }
    const committedPath = outcome.committedPath;
    return {
        baseline: { title: basenameVirtualPath(committedPath), content: draft.content, promptColor: null },
        sourceReference: { type: 'path', value: committedPath },
        headerDescription: resolveFileExplorerPreviewHeaderDescriptionForFile(mimeType),
        openSourceUrl: buildFileExplorerSourceUrl(committedPath)
    };
};

const openFileExplorerContentPreview = async (api: FileExplorerContentPreviewApi, path: string): Promise<boolean> => {
    const sequence = fileExplorerPreviewSequence + 1;
    fileExplorerPreviewSequence = sequence;
    try {
        const metadata = parseFileBrowserMetadataPayload(await api.fileExplorer.metadata(toVirtualPath(path), { includeHash: false }));
        if (!isCurrentFileExplorerPreviewRequest(sequence)) {
            return true;
        }
        if (metadata.isDirectory) {
            return false;
        }
        const sourceReference = createSourceReference(metadata);
        const openSourceUrl = buildFileExplorerSourceUrl(metadata.path);
        const mediaType = classifyFileBrowserMimeType(metadata.mimeType);
        const headerDescription = resolveFileExplorerPreviewHeaderDescription(metadata);
        if (mediaType === 'text') {
            const readPayload = parseFileBrowserReadPayload(await api.fileExplorer.read(metadata.path));
            if (!isCurrentFileExplorerPreviewRequest(sequence)) {
                return true;
            }
            let currentPath = readPayload.path;
            requireContentPreviewModalService().open(
                createTextContentPreviewRequest({
                    scope: 'fileExplorer',
                    type: 'text',
                    headerDescription,
                    baseline: { title: metadata.name, content: readPayload.content, promptColor: null },
                    editable: true,
                    languageMode: 'default',
                    disableCopyWhenEmpty: false,
                    disableDownloadWhenEmpty: false,
                    colorToolkit: null,
                    sourceReference,
                    onRequestSave: async (draft): Promise<ContentPreviewTextSaveResult | null> => {
                        const saveResult = await saveFileExplorerPreviewText(api, currentPath, metadata.mimeType, draft, () => isCurrentFileExplorerPreviewRequest(sequence));
                        if (saveResult?.sourceReference) {
                            currentPath = saveResult.sourceReference.value;
                        }
                        return saveResult;
                    },
                    onRequestDownload: async (): Promise<void> => await downloadFileExplorerPreviewPath(api, currentPath),
                    onRequestCopy: async (text): Promise<void> => await copyFileExplorerPreviewText(text),
                    onRequestAttach: async (): Promise<void> => await copySoaiPathLinkToClipboard(currentPath),
                    enhance: null,
                    openSourceUrl,
                    onStatePotentiallyChanged: null
                })
            );
            return true;
        }
        if (mediaType === 'image' || mediaType === 'audio' || mediaType === 'video') {
            requireContentPreviewModalService().open(
                createMediaContentPreviewRequest({
                    scope: 'fileExplorer',
                    type: mediaType,
                    headerDescription,
                    title: metadata.name,
                    sourceUrl: buildFileExplorerPreviewUrl(metadata.path, false),
                    imageMetadata: { contentType: metadata.mimeType, contentLength: metadata.size },
                    sourceReference,
                    onRequestDownload: async (): Promise<void> => await downloadFileExplorerPreviewPath(api, metadata.path),
                    onRequestAttach: async (): Promise<void> => await copySoaiPathLinkToClipboard(metadata.path),
                    openSourceUrl
                })
            );
            return true;
        }
        requireContentPreviewModalService().open(
            createDocumentContentPreviewRequest({
                scope: 'fileExplorer',
                type: mediaType === 'document' ? 'document' : 'file',
                headerDescription,
                title: metadata.name,
                sourceReference,
                onRequestDownload: async (): Promise<void> => await downloadFileExplorerPreviewPath(api, metadata.path),
                onRequestAttach: async (): Promise<void> => await copySoaiPathLinkToClipboard(metadata.path),
                openSourceUrl
            })
        );
        return true;
    } catch (error) {
        if (!isCurrentFileExplorerPreviewRequest(sequence)) {
            return true;
        }
        throw ensureError(error);
    }
};

export { cancelFileExplorerContentPreviewRequest, isFileExplorerContentPreviewApi, openFileExplorerContentPreview };
export type { FileExplorerContentPreviewApi };
