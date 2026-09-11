/* SoAI - Shared file explorer browser contracts [frontend/assets/ts/core/fileexplorerbrowser/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { FileExplorerListResponse, FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import type { HostFilesystemLocateResponse, HostFilesystemRootsResponse } from '@core/api/contracts/hostFilesystemBrowserContracts.ts';
import type { FileEntryTypeId } from '@core/fileexplorerbrowser/entryTypeMappings.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

interface FileBrowserListOptions {
    path?: string;
    offset?: number;
    limit?: number;
    signal?: AbortSignal;
}

interface FileBrowserSearchOptions {
    path?: string;
    query: string;
    offset?: number;
    limit?: number;
    caseSensitive?: boolean;
    includeTotal?: boolean;
    signal?: AbortSignal;
}

interface HostFileBrowserListOptions extends FileBrowserListOptions {
    rootPath?: string;
}

interface HostFileBrowserSearchOptions extends FileBrowserSearchOptions {
    rootPath?: string;
}

interface ReadOnlyFileBrowserApi {
    list(options?: FileBrowserListOptions): Promise<FileExplorerListResponse>;
    search(options: FileBrowserSearchOptions): Promise<FileExplorerSearchResponse>;
}

interface HostFilesystemBrowserApi {
    roots(options?: { signal?: AbortSignal }): Promise<HostFilesystemRootsResponse>;
    locate(path: string, options?: { signal?: AbortSignal }): Promise<HostFilesystemLocateResponse>;
    list(options: HostFileBrowserListOptions): Promise<FileExplorerListResponse>;
    search(options: HostFileBrowserSearchOptions): Promise<FileExplorerSearchResponse>;
}

type FileBrowserSource = { type: 'workspace'; api: ReadOnlyFileBrowserApi } | { type: 'host'; api: HostFilesystemBrowserApi };

interface FileBrowserEntry {
    path: string;
    name: string;
    isDirectory: boolean;
    size: number;
    modifiedAt: string;
    modifiedAtTimestamp: number;
    mimeType: string;
    typeId: FileEntryTypeId;
    typeRank: number;
    permissions: string;
}

interface FileBrowserMetadata {
    path: string;
    name: string;
    isDirectory: boolean;
    size: number;
    modifiedAt: string;
    mimeType: string;
    typeId: FileEntryTypeId;
    typeRank: number;
    permissions: string;
    sha256: string | null;
}

type FileBrowserRecord = FileBrowserEntry | FileBrowserMetadata;

interface FileBrowserReadPayload {
    path: string;
    content: string;
}

interface FileBrowserListPayload {
    path: string;
    entries: FileBrowserEntry[];
    total: number;
    offset: number;
    limit: number;
}

type FileBrowserMediaType = 'audio' | 'document' | 'file' | 'image' | 'text' | 'video';

interface FileBrowserState {
    currentPath: string;
    workspacePathResolved: string | null;
    query: string;
    entries: readonly FileBrowserEntry[];
    truncated: boolean;
    isLoading: boolean;
    errorMessage: string | null;
}

interface DirectoryBrowserState extends FileBrowserState {
    rootPaths: readonly string[];
    pendingRootPath: string | null;
    canConfirm: boolean;
}

interface DirectoryListingBrowserState extends FileBrowserState {
    sessionRevision: number;
    total: number;
    hasMore: boolean;
    nextOffset: number | null;
    isLoadingMore: boolean;
}

interface FileBrowserLoadResponse {
    currentPath: string;
    workspacePathResolved: string | null;
    query: string;
    entries: readonly FileBrowserEntry[];
    truncated: boolean;
}

interface FileBrowserErrorResolver {
    resolve(error: Error): string;
}

interface FileBrowserIconResolver {
    getIconSync(name: IconName, options?: IconOptions): TrustedHtml;
}

export type { DirectoryBrowserState, DirectoryListingBrowserState, FileBrowserEntry, FileBrowserErrorResolver, FileBrowserIconResolver, FileBrowserListOptions, FileBrowserListPayload, FileBrowserLoadResponse, FileBrowserMediaType, FileBrowserMetadata, FileBrowserReadPayload, FileBrowserRecord, FileBrowserSearchOptions, FileBrowserSource, FileBrowserState, HostFileBrowserListOptions, HostFileBrowserSearchOptions, HostFilesystemBrowserApi, ReadOnlyFileBrowserApi };
