/* SoAI - Shared API file explorer [frontend/assets/ts/core/api/endpoints/fileExplorer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { FILE_EXPLORER_BASE_PATH } from '@core/api/endpoints/fileExplorerPaths.ts';
import { buildSignalRequestOptions, normalizeNonEmptyRequestStrings, requireNonEmptyRequestString } from '@core/api/requestOptions.ts';
import { FILE_TRANSFER_REQUEST_TIMEOUT_MS } from '@core/api/fileTransferTimeout.ts';
import { decodeBufferedFileResponse, decodeFileExplorerBatchMetadataResponse, decodeFileExplorerBatchResponse, decodeFileExplorerBatchUploadResponse, decodeFileExplorerListResponse, decodeFileExplorerMetadataResponse, decodeFileExplorerMoveMutationResponse, decodeFileExplorerPathMutationResponse, decodeFileExplorerReadResponse, decodeFileExplorerSearchResponse, decodeFileExplorerTaskAcceptedResponse, decodeFileExplorerUploadResponse, serializeFileExplorerBatchMoveRequest } from '@core/api/contracts/fileExplorerContracts.ts';
import type { FileExplorerBatchMetadataResponse, FileExplorerBatchResponse, FileExplorerBatchUploadResponse, FileExplorerListResponse, FileExplorerMetadataResponse, FileExplorerMoveMutationResponse, FileExplorerPathMutationResponse, FileExplorerReadResponse, FileExplorerSearchResponse, FileExplorerTaskAcceptedResponse, FileExplorerUploadResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import type { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import { createFileExplorerListingEndpoints, type FileExplorerListingEndpoints } from '@core/api/endpoints/fileExplorerListingEndpoints.ts';

interface FileExplorerRequestOptions {
    signal?: AbortSignal;
}

interface FileExplorerListOptions extends FileExplorerRequestOptions {
    path?: string;
    offset?: number;
    limit?: number;
}

interface FileExplorerMetadataOptions extends FileExplorerRequestOptions {
    includeHash?: boolean;
}

interface FileExplorerSearchOptions extends FileExplorerRequestOptions {
    path?: string;
    query: string;
    offset?: number;
    limit?: number;
    caseSensitive?: boolean;
    includeTotal?: boolean;
}

const requireNonEmpty = (value: string, field: string): string => requireNonEmptyRequestString(value, field, 'fileExplorer');

const normalizePaths = (values: readonly string[], field: string): string[] => normalizeNonEmptyRequestStrings(values, field, 'fileExplorer');

const requestOptions = (options: FileExplorerRequestOptions = {}): { signal?: AbortSignal } => buildSignalRequestOptions(options);

const createFileExplorerEndpoints = (
    api: ApiClientContext
): {
    list: (options?: FileExplorerListOptions) => Promise<FileExplorerListResponse>;
    metadata: (path: string, options?: FileExplorerMetadataOptions) => Promise<FileExplorerMetadataResponse>;
    read: (path: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerReadResponse>;
    batchMetadata: (paths: readonly string[], options?: FileExplorerRequestOptions) => Promise<FileExplorerBatchMetadataResponse>;
    hash: (path: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerTaskAcceptedResponse>;
    search: (options: FileExplorerSearchOptions) => Promise<FileExplorerSearchResponse>;
    write: (path: string, content: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerPathMutationResponse>;
    mkdir: (path: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerPathMutationResponse>;
    delete: (path: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerPathMutationResponse>;
    batchDelete: (paths: readonly string[], options?: FileExplorerRequestOptions) => Promise<FileExplorerBatchResponse>;
    batchDeleteTask: (paths: readonly string[], options?: FileExplorerRequestOptions) => Promise<FileExplorerTaskAcceptedResponse>;
    move: (source: string, destination: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerMoveMutationResponse>;
    batchMove: (sources: readonly string[], destinationDir: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerBatchResponse>;
    batchMoveTask: (sources: readonly string[], destinationDir: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerTaskAcceptedResponse>;
    copy: (source: string, destination: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerMoveMutationResponse>;
    batchCopy: (sources: readonly string[], destinationDir: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerBatchResponse>;
    batchCopyTask: (sources: readonly string[], destinationDir: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerTaskAcceptedResponse>;
    download: (path: string, options?: FileExplorerRequestOptions) => Promise<BufferedApiResponse>;
    downloadSelection: (paths: readonly string[], options?: FileExplorerRequestOptions) => Promise<BufferedApiResponse>;
    upload: (file: File, path: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerUploadResponse>;
    uploadBatch: (files: readonly File[], relativePaths: readonly string[], path: string, options?: FileExplorerRequestOptions) => Promise<FileExplorerBatchUploadResponse>;
} & FileExplorerListingEndpoints => {
    return {
        ...createFileExplorerListingEndpoints(api),
        list: async (options: FileExplorerListOptions = {}): Promise<FileExplorerListResponse> =>
            decodeFileExplorerListResponse(
                await api.get(`${FILE_EXPLORER_BASE_PATH}/list`, {
                    ...requestOptions(options),
                    query: {
                        path: options.path ?? '/',
                        offset: options.offset,
                        limit: options.limit
                    }
                })
            ),
        metadata: async (path: string, options: FileExplorerMetadataOptions = {}): Promise<FileExplorerMetadataResponse> =>
            decodeFileExplorerMetadataResponse(
                await api.get(`${FILE_EXPLORER_BASE_PATH}/metadata`, {
                    ...requestOptions(options),
                    query: {
                        path: requireNonEmpty(path, 'metadata.path'),
                        'include_hash': options.includeHash
                    }
                })
            ),
        read: async (path: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerReadResponse> =>
            decodeFileExplorerReadResponse(
                await api.get(`${FILE_EXPLORER_BASE_PATH}/read`, {
                    ...requestOptions(options),
                    query: { path: requireNonEmpty(path, 'read.path') }
                })
            ),
        batchMetadata: async (paths: readonly string[], options: FileExplorerRequestOptions = {}): Promise<FileExplorerBatchMetadataResponse> =>
            decodeFileExplorerBatchMetadataResponse(
                await api.post(
                    `${FILE_EXPLORER_BASE_PATH}/batch-metadata`,
                    { paths: normalizePaths(paths, 'batchMetadata.paths') },
                    {
                        ...requestOptions(options)
                    }
                )
            ),
        hash: async (path: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerTaskAcceptedResponse> =>
            decodeFileExplorerTaskAcceptedResponse(
                await api.post(`${FILE_EXPLORER_BASE_PATH}/hash`, undefined, {
                    ...requestOptions(options),
                    query: { path: requireNonEmpty(path, 'hash.path') }
                })
            ),
        search: async (options: FileExplorerSearchOptions): Promise<FileExplorerSearchResponse> =>
            decodeFileExplorerSearchResponse(
                await api.get(`${FILE_EXPLORER_BASE_PATH}/search`, {
                    ...requestOptions(options),
                    query: {
                        path: options.path ?? '/',
                        query: requireNonEmpty(options.query, 'search.query'),
                        offset: options.offset,
                        limit: options.limit,
                        'case_sensitive': options.caseSensitive,
                        'include_total': options.includeTotal
                    }
                })
            ),
        write: async (path: string, content: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerPathMutationResponse> => decodeFileExplorerPathMutationResponse(await api.put(`${FILE_EXPLORER_BASE_PATH}/write`, { path: requireNonEmpty(path, 'write.path'), content }, requestOptions(options))),
        mkdir: async (path: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerPathMutationResponse> => decodeFileExplorerPathMutationResponse(await api.post(`${FILE_EXPLORER_BASE_PATH}/mkdir`, { path: requireNonEmpty(path, 'mkdir.path') }, requestOptions(options))),
        delete: async (path: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerPathMutationResponse> =>
            decodeFileExplorerPathMutationResponse(
                await api.delete(`${FILE_EXPLORER_BASE_PATH}/delete`, {
                    ...requestOptions(options),
                    body: { path: requireNonEmpty(path, 'delete.path') }
                })
            ),
        batchDelete: async (paths: readonly string[], options: FileExplorerRequestOptions = {}): Promise<FileExplorerBatchResponse> =>
            decodeFileExplorerBatchResponse(
                await api.post(
                    `${FILE_EXPLORER_BASE_PATH}/batch-delete`,
                    { paths: normalizePaths(paths, 'batchDelete.paths') },
                    {
                        ...requestOptions(options)
                    }
                )
            ),
        batchDeleteTask: async (paths: readonly string[], options: FileExplorerRequestOptions = {}): Promise<FileExplorerTaskAcceptedResponse> =>
            decodeFileExplorerTaskAcceptedResponse(
                await api.post(
                    `${FILE_EXPLORER_BASE_PATH}/batch-delete-task`,
                    { paths: normalizePaths(paths, 'batchDeleteTask.paths') },
                    {
                        ...requestOptions(options)
                    }
                )
            ),
        move: async (source: string, destination: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerMoveMutationResponse> =>
            decodeFileExplorerMoveMutationResponse(
                await api.post(
                    `${FILE_EXPLORER_BASE_PATH}/move`,
                    {
                        source: requireNonEmpty(source, 'move.source'),
                        destination: requireNonEmpty(destination, 'move.destination')
                    },
                    requestOptions(options)
                )
            ),
        batchMove: async (sources: readonly string[], destinationDir: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerBatchResponse> => decodeFileExplorerBatchResponse(await api.post(`${FILE_EXPLORER_BASE_PATH}/batch-move`, serializeFileExplorerBatchMoveRequest(normalizePaths(sources, 'batchMove.sources'), requireNonEmpty(destinationDir, 'batchMove.destination_dir')), requestOptions(options))),
        batchMoveTask: async (sources: readonly string[], destinationDir: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerTaskAcceptedResponse> => decodeFileExplorerTaskAcceptedResponse(await api.post(`${FILE_EXPLORER_BASE_PATH}/batch-move-task`, serializeFileExplorerBatchMoveRequest(normalizePaths(sources, 'batchMoveTask.sources'), requireNonEmpty(destinationDir, 'batchMoveTask.destination_dir')), requestOptions(options))),
        copy: async (source: string, destination: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerMoveMutationResponse> =>
            decodeFileExplorerMoveMutationResponse(
                await api.post(
                    `${FILE_EXPLORER_BASE_PATH}/copy`,
                    {
                        source: requireNonEmpty(source, 'copy.source'),
                        destination: requireNonEmpty(destination, 'copy.destination')
                    },
                    requestOptions(options)
                )
            ),
        batchCopy: async (sources: readonly string[], destinationDir: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerBatchResponse> => decodeFileExplorerBatchResponse(await api.post(`${FILE_EXPLORER_BASE_PATH}/batch-copy`, serializeFileExplorerBatchMoveRequest(normalizePaths(sources, 'batchCopy.sources'), requireNonEmpty(destinationDir, 'batchCopy.destination_dir')), requestOptions(options))),
        batchCopyTask: async (sources: readonly string[], destinationDir: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerTaskAcceptedResponse> => decodeFileExplorerTaskAcceptedResponse(await api.post(`${FILE_EXPLORER_BASE_PATH}/batch-copy-task`, serializeFileExplorerBatchMoveRequest(normalizePaths(sources, 'batchCopyTask.sources'), requireNonEmpty(destinationDir, 'batchCopyTask.destination_dir')), requestOptions(options))),
        download: async (path: string, options: FileExplorerRequestOptions = {}): Promise<BufferedApiResponse> =>
            decodeBufferedFileResponse(
                await api.get(`${FILE_EXPLORER_BASE_PATH}/download`, {
                    ...requestOptions(options),
                    query: { path: requireNonEmpty(path, 'download.path') },
                    rawResponse: true,
                    bufferRawResponse: true,
                    timeoutMs: FILE_TRANSFER_REQUEST_TIMEOUT_MS
                })
            ),
        downloadSelection: async (paths: readonly string[], options: FileExplorerRequestOptions = {}): Promise<BufferedApiResponse> =>
            decodeBufferedFileResponse(
                await api.post(
                    `${FILE_EXPLORER_BASE_PATH}/download-selection`,
                    { paths: normalizePaths(paths, 'downloadSelection.paths') },
                    {
                        ...requestOptions(options),
                        rawResponse: true,
                        bufferRawResponse: true,
                        timeoutMs: FILE_TRANSFER_REQUEST_TIMEOUT_MS
                    }
                )
            ),
        upload: async (file: File, path: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerUploadResponse> => {
            const destinationPath = requireNonEmpty(path, 'upload.path');
            const formData = new FormData();
            formData.append('size_bytes', String(file.size));
            if (file.type) {
                formData.append('content_type', file.type);
            }
            formData.append('file', file);
            return decodeFileExplorerUploadResponse(
                await api.post(`${FILE_EXPLORER_BASE_PATH}/upload`, formData, {
                    ...requestOptions(options),
                    headers: {},
                    timeoutMs: FILE_TRANSFER_REQUEST_TIMEOUT_MS,
                    query: { path: destinationPath }
                })
            );
        },
        uploadBatch: async (files: readonly File[], relativePaths: readonly string[], path: string, options: FileExplorerRequestOptions = {}): Promise<FileExplorerBatchUploadResponse> => {
            if (files.length <= 0) {
                throw new Error('fileExplorer.uploadBatch requires at least one file');
            }
            if (files.length !== relativePaths.length) {
                throw new Error('fileExplorer.uploadBatch requires relativePaths to match files length');
            }
            const destinationPath = requireNonEmpty(path, 'uploadBatch.path');
            const normalizedRelativePaths = normalizePaths(relativePaths, 'uploadBatch.relativePaths');
            const formData = new FormData();
            formData.append('relative_paths', JSON.stringify(normalizedRelativePaths));
            formData.append('relative_sizes', JSON.stringify(files.map((file) => file.size)));
            files.forEach((file) => formData.append('files', file));
            return decodeFileExplorerBatchUploadResponse(
                await api.post(`${FILE_EXPLORER_BASE_PATH}/upload-batch`, formData, {
                    ...requestOptions(options),
                    headers: {},
                    timeoutMs: FILE_TRANSFER_REQUEST_TIMEOUT_MS,
                    query: { path: destinationPath }
                })
            );
        }
    };
};

export { createFileExplorerEndpoints };
