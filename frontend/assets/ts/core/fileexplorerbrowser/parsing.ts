/* SoAI - Shared file explorer browser parsing [frontend/assets/ts/core/fileexplorerbrowser/parsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerListResponse, FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { formatDateTime } from '@core/primitives/dateTime.ts';
import { joinVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { FileBrowserEntry, FileBrowserLoadResponse } from '@core/fileexplorerbrowser/types.ts';
type FileExplorerBrowserResponse = FileExplorerListResponse | FileExplorerSearchResponse;

const parseTruncated = (payload: FileExplorerBrowserResponse, entryCount: number): boolean => {
    if ('truncated' in payload) return payload.truncated;
    return payload.total > payload.offset + entryCount;
};

const parseWorkspacePathResolved = (payload: FileExplorerBrowserResponse): string => payload.workspacePathResolved;

const parseFileBrowserEntriesPayload = (payload: FileExplorerBrowserResponse, currentPath: string, hasSearchQuery: boolean): FileBrowserEntry[] => {
    return payload.entries.map((entryValue) => {
        const name = entryValue.name;
        const path = hasSearchQuery && 'path' in entryValue ? toVirtualPath(entryValue.path) : joinVirtualPath(currentPath, name);
        const modifiedAtRaw = entryValue.modifiedAtMs;
        return {
            path,
            name,
            isDirectory: entryValue.isDirectory,
            size: entryValue.size,
            modifiedAt: formatDateTime(modifiedAtRaw, true),
            modifiedAtTimestamp: modifiedAtRaw,
            mimeType: entryValue.mimeType,
            typeId: entryValue.typeId,
            typeRank: entryValue.typeRank,
            permissions: entryValue.permissions
        };
    });
};

const parseFileBrowserLoadResponse = (payload: FileExplorerBrowserResponse, query: string): FileBrowserLoadResponse => {
    const normalizedQuery = query.trim();
    const resolvedCurrentPath = 'searchRoot' in payload ? toVirtualPath(payload.searchRoot) : toVirtualPath(payload.path);
    const entries = parseFileBrowserEntriesPayload(payload, resolvedCurrentPath, normalizedQuery.length > 0);
    const workspacePathResolved = parseWorkspacePathResolved(payload);
    const truncated = parseTruncated(payload, entries.length);
    return {
        currentPath: resolvedCurrentPath,
        workspacePathResolved,
        query: normalizedQuery,
        entries,
        truncated
    };
};

export { parseFileBrowserEntriesPayload, parseFileBrowserLoadResponse, parseWorkspacePathResolved };
