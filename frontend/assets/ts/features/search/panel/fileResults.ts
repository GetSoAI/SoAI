/* SoAI - Search feature file results [frontend/assets/ts/features/search/panel/fileResults.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleApiResult } from '@core/api/apiResultHandler.ts';
import type { FileExplorerMetadataResponse, FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { APIError } from '@core/apiError.ts';
import { resolveFileEntryIconName } from '@core/fileexplorerbrowser/entryIconResolution.ts';
import { resolveFileEntryTypeLabel } from '@core/fileexplorerbrowser/entryTypeLabels.ts';
import { parseFileBrowserLoadResponse } from '@core/fileexplorerbrowser/parsing.ts';
import { parseFileBrowserMetadataPayload } from '@core/fileexplorerbrowser/payloads.ts';
import { resolveAbsolutePath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { FileBrowserRecord, FileBrowserSearchOptions } from '@core/fileexplorerbrowser/types.ts';
import { isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import type { SearchItem, SearchOptions } from '@core/search/searchTypes.ts';

interface FileSearchApiClient {
    fileExplorer: {
        metadata(path: string, options?: { includeHash?: boolean; signal?: AbortSignal }): Promise<FileExplorerMetadataResponse>;
        search(options: FileBrowserSearchOptions): Promise<FileExplorerSearchResponse>;
    };
}

interface FileSearchContext {
    apiClient: FileSearchApiClient;
}

const mapFileSearchEntry = (entry: FileBrowserRecord, workspacePathResolved: string | null): SearchItem => {
    const filePath = entry.path;
    const entryType = entry.isDirectory ? 'directory' : 'file';
    const displayPath = resolveAbsolutePath(workspacePathResolved, filePath) ?? filePath;
    return {
        id: filePath,
        name: entry.name,
        description: displayPath,
        type: 'files',
        category: 'files',
        badge: resolveFileEntryTypeLabel(entry.typeId),
        icon: resolveFileEntryIconName(entry),
        filePath: filePath,
        fileEntryType: entryType
    };
};

const searchFileExplorerResults = async (context: FileSearchContext, query: string, limit: number, options: SearchOptions = {}): Promise<SearchItem[]> => {
    const normalizedQuery = normalizeSearchDisplayQuery(query);
    if (!normalizedQuery || normalizedQuery.length < 2) {
        return [];
    }
    throwIfAborted(options.signal);
    const response = await handleApiResult(
        context.apiClient.fileExplorer.search({
            path: '/',
            query: normalizedQuery,
            limit,
            includeTotal: false,
            ...(options.signal ? { signal: options.signal } : {})
        }),
        {
            boundaryName: 'SearchPanel.fileExplorer',
            silent: true,
            notifyOnError: false,
            rethrow: (error) => isAbortError(error),
            logErrors: false
        }
    );
    throwIfAborted(options.signal);
    if (response === null) {
        throw new TypeError('File search response is required.');
    }
    const parsed = parseFileBrowserLoadResponse(response, normalizedQuery);
    return parsed.entries.map((entry) => mapFileSearchEntry(entry, parsed.workspacePathResolved));
};

const resolveSoaiPathFileResult = async (context: FileSearchContext, virtualPath: string, options: SearchOptions = {}): Promise<SearchItem[]> => {
    throwIfAborted(options.signal);
    try {
        const response = await context.apiClient.fileExplorer.metadata(toVirtualPath(virtualPath), { includeHash: false, ...(options.signal ? { signal: options.signal } : {}) });
        throwIfAborted(options.signal);
        return [mapFileSearchEntry(parseFileBrowserMetadataPayload(response), null)];
    } catch (error) {
        if (error instanceof APIError && error.status === 404) {
            return [];
        }
        throw error;
    }
};

export { resolveSoaiPathFileResult, searchFileExplorerResults };
export type { FileSearchApiClient, FileSearchContext };
