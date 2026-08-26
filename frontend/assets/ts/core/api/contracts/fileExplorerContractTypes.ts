/* SoAI - File explorer API payload type declarations [frontend/assets/ts/core/api/contracts/fileExplorerContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileEntryTypeId } from '@core/fileexplorerbrowser/entryTypeMappings.ts';

interface FileExplorerEntryResponse {
    name: string;
    isDirectory: boolean;
    size: number;
    modifiedAtMs: number;
    mimeType: string;
    typeId: FileEntryTypeId;
    typeRank: number;
    permissions: string;
}

interface FileExplorerSearchEntryResponse extends FileExplorerEntryResponse {
    path: string;
}

interface FileExplorerListResponse {
    path: string;
    entries: FileExplorerEntryResponse[];
    total: number;
    offset: number;
    limit: number;
    workspacePathResolved: string;
}

interface FileExplorerSearchResponse {
    query: string;
    searchRoot: string;
    entries: FileExplorerSearchEntryResponse[];
    total: number;
    offset: number;
    limit: number;
    truncated: boolean;
    scannedEntries: number;
    workspacePathResolved: string;
}

interface FileExplorerMetadataResponse {
    name: string;
    path: string;
    isDirectory: boolean;
    size: number;
    modifiedAtMs: number;
    mimeType: string;
    typeId: FileEntryTypeId;
    typeRank: number;
    permissions: string;
    sha256: string | null;
}

interface FileExplorerReadResponse {
    path: string;
    content: string;
}

interface FileExplorerBatchItemResponse {
    path: string;
    success: boolean;
    error: string | null;
}

interface FileExplorerBatchMetadataItemResponse extends FileExplorerBatchItemResponse {
    metadata: FileExplorerMetadataResponse | null;
}

interface FileExplorerBatchResponse {
    status: 'ok';
    total: number;
    succeeded: number;
    failed: number;
    results: FileExplorerBatchItemResponse[];
    destination?: string;
}

interface FileExplorerBatchMetadataResponse {
    status: 'ok';
    total: number;
    succeeded: number;
    failed: number;
    results: FileExplorerBatchMetadataItemResponse[];
}

interface FileExplorerPathMutationResponse {
    status: 'ok';
    path: string;
}

interface FileExplorerMoveMutationResponse {
    status: 'ok';
    source: string;
    destination: string;
}

interface FileExplorerTaskAcceptedResponse {
    status: 'accepted';
    taskId: string;
}

interface FileExplorerUploadResponse {
    status: 'ok';
    path: string;
    size: number;
    taskId: string;
}

interface FileExplorerBatchUploadItemResponse {
    path: string;
    success: boolean;
    size?: number;
    error?: string;
}

interface FileExplorerBatchUploadResponse {
    status: 'ok';
    taskId: string;
    total: number;
    succeeded: number;
    failed: number;
    totalSize: number;
    results: FileExplorerBatchUploadItemResponse[];
}

export type { FileExplorerBatchItemResponse, FileExplorerBatchMetadataItemResponse, FileExplorerBatchMetadataResponse, FileExplorerBatchResponse, FileExplorerBatchUploadItemResponse, FileExplorerBatchUploadResponse, FileExplorerEntryResponse, FileExplorerListResponse, FileExplorerMetadataResponse, FileExplorerMoveMutationResponse, FileExplorerPathMutationResponse, FileExplorerReadResponse, FileExplorerSearchEntryResponse, FileExplorerSearchResponse, FileExplorerTaskAcceptedResponse, FileExplorerUploadResponse };
