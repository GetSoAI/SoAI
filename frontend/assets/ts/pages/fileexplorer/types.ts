/* SoAI - File explorer page public contracts [frontend/assets/ts/pages/fileexplorer/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import type { FileExplorerBatchResponse, FileExplorerBatchUploadResponse, FileExplorerListResponse, FileExplorerMetadataResponse, FileExplorerMoveMutationResponse, FileExplorerPathMutationResponse, FileExplorerReadResponse, FileExplorerSearchResponse, FileExplorerTaskAcceptedResponse, FileExplorerUploadResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { DirectoryListingApi } from '@core/fileexplorerbrowser/directoryListingController.ts';

interface FileExplorerListOptions {
    path?: string;
    offset?: number;
    limit?: number;
    signal?: AbortSignal;
}

interface FileExplorerSearchOptions {
    path?: string;
    query: string;
    offset?: number;
    limit?: number;
    caseSensitive?: boolean;
    includeTotal?: boolean;
    signal?: AbortSignal;
}

interface FileExplorerRequestOptions {
    signal?: AbortSignal;
}

interface FileExplorerApi extends DirectoryListingApi {
    list(options?: FileExplorerListOptions): Promise<FileExplorerListResponse>;
    search(options: FileExplorerSearchOptions): Promise<FileExplorerSearchResponse>;
    metadata(path: string, options?: FileExplorerRequestOptions): Promise<FileExplorerMetadataResponse>;
    read(path: string, options?: FileExplorerRequestOptions): Promise<FileExplorerReadResponse>;
    write(path: string, content: string, options?: FileExplorerRequestOptions): Promise<FileExplorerPathMutationResponse>;
    mkdir(path: string, options?: FileExplorerRequestOptions): Promise<FileExplorerPathMutationResponse>;
    delete(path: string, options?: FileExplorerRequestOptions): Promise<FileExplorerPathMutationResponse>;
    batchDelete(paths: readonly string[], options?: FileExplorerRequestOptions): Promise<FileExplorerBatchResponse>;
    batchDeleteTask(paths: readonly string[], options?: FileExplorerRequestOptions): Promise<FileExplorerTaskAcceptedResponse>;
    move(source: string, destination: string, options?: FileExplorerRequestOptions): Promise<FileExplorerMoveMutationResponse>;
    batchMove(sources: readonly string[], destinationDir: string, options?: FileExplorerRequestOptions): Promise<FileExplorerBatchResponse>;
    batchMoveTask(sources: readonly string[], destinationDir: string, options?: FileExplorerRequestOptions): Promise<FileExplorerTaskAcceptedResponse>;
    copy(source: string, destination: string, options?: FileExplorerRequestOptions): Promise<FileExplorerMoveMutationResponse>;
    batchCopy(sources: readonly string[], destinationDir: string, options?: FileExplorerRequestOptions): Promise<FileExplorerBatchResponse>;
    batchCopyTask(sources: readonly string[], destinationDir: string, options?: FileExplorerRequestOptions): Promise<FileExplorerTaskAcceptedResponse>;
    hash(path: string, options?: FileExplorerRequestOptions): Promise<FileExplorerTaskAcceptedResponse>;
    download(path: string, options?: FileExplorerRequestOptions): Promise<BufferedApiResponse>;
    downloadSelection(paths: readonly string[], options?: FileExplorerRequestOptions): Promise<BufferedApiResponse>;
    upload(file: File, path: string, options?: FileExplorerRequestOptions): Promise<FileExplorerUploadResponse>;
    uploadBatch(files: readonly File[], relativePaths: readonly string[], path: string, options?: FileExplorerRequestOptions): Promise<FileExplorerBatchUploadResponse>;
}

interface FileExplorerControllerHost {
    api: FileExplorerApi;
    awaitTask: (taskId: string, signal: AbortSignal) => Promise<void>;
    showNotification: (message: string, type: NotificationType) => void;
    handleError: (error: Error, context: string, options?: { notify?: boolean }) => void;
    getIconSync: (name: IconName, options?: IconOptions) => TrustedHtml;
}

interface FileExplorerSelectionProvider {
    getCurrentPath: () => string;
    getSelectedPaths: () => readonly string[];
    refresh: (uploadSession?: FileExplorerUploadMarkerSession) => Promise<void>;
}

interface FileExplorerSelectionSnapshot {
    currentPath: string;
    revision: number;
    selectedPaths: readonly string[];
}

interface FileExplorerUploadMarkerSession {
    currentPath: string;
    revision: number;
}

interface FileExplorerUploadUi {
    uploadFilesInput: HTMLInputElement;
    uploadFolderInput: HTMLInputElement;
}

interface FileExplorerUiRefs {
    root: HTMLElement;
    breadcrumb: HTMLElement;
    currentPathInput: HTMLInputElement;
    currentPathSaveButton: HTMLButtonElement;
    resultCount: HTMLElement;
    selectionCount: HTMLElement;
    selectionStatusBadge: HTMLElement;
    navigateHomeButton: HTMLButtonElement;
    navigatePreviousButton: HTMLButtonElement;
    navigateNextButton: HTMLButtonElement;
    navigateUpButton: HTMLButtonElement;
    rowsBody: HTMLTableSectionElement;
    selectAllToggle: HTMLInputElement;
    uploadFilesInput: HTMLInputElement;
    uploadFolderInput: HTMLInputElement;

    sortSelect: HTMLSelectElement;
    sortShell: HTMLElement;
    newEntryShell: HTMLElement;
    viewModeToggleButton: HTMLButtonElement;
    selectionSelectAllButton: HTMLButtonElement;
    selectionDeselectAllButton: HTMLButtonElement;
    selectionInverseButton: HTMLButtonElement;
    toggleSelectionModeButton: HTMLButtonElement;

    selectionMetadataButton: HTMLButtonElement;
    selectionRenameButton: HTMLButtonElement;
    selectionSoaiLinkButton: HTMLButtonElement;
    selectionCopyButton: HTMLButtonElement;
    selectionMoveButton: HTMLButtonElement;
    selectionDeleteButton: HTMLButtonElement;
    selectionDownloadButton: HTMLButtonElement;
    copyHereButton: HTMLButtonElement;
    moveHereButton: HTMLButtonElement;
    transferCancelButton: HTMLButtonElement;

    taskPanel: HTMLElement;
    taskToggleButton: HTMLButtonElement;
    taskCount: HTMLElement;
    taskLabel: HTMLElement;
    taskDetails: HTMLElement;
    taskSummaryBar: HTMLElement;
    taskSummaryBarFill: HTMLElement;
    taskSummaryValue: HTMLElement;
    taskId: HTMLElement;
    taskProgress: HTMLElement;
}

export type { FileExplorerApi, FileExplorerControllerHost, FileExplorerListOptions, FileExplorerRequestOptions, FileExplorerSearchOptions, FileExplorerSelectionProvider, FileExplorerSelectionSnapshot, FileExplorerUiRefs, FileExplorerUploadMarkerSession, FileExplorerUploadUi };
