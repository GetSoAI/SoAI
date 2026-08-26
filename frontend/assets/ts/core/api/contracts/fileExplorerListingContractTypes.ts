/* SoAI - File explorer listing payload type declarations [frontend/assets/ts/core/api/contracts/fileExplorerListingContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerEntryResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';

type FileExplorerListingEntryType = 'all' | 'directory' | 'file';
type FileExplorerListingSortColumn = 'modified' | 'name' | 'size' | 'type';
type FileExplorerListingSortDirection = 'asc' | 'desc';

interface FileExplorerListingAcceptedResponse {
    status: 'accepted';
    listingId: string;
    taskId: string;
    path: string;
}

interface FileExplorerListingPageResponse {
    listingId: string;
    path: string;
    entries: FileExplorerEntryResponse[];
    total: number;
    offset: number;
    limit: number;
    hasMore: boolean;
    nextOffset: number | null;
    workspacePathResolved: string;
}

interface FileExplorerListingLocateResponse {
    offset: number;
}

interface FileExplorerListingReleasedResponse {
    status: 'released';
    listingId: string;
}

interface FileExplorerListingPageOptions {
    offset: number;
    limit: number;
    sortColumn: FileExplorerListingSortColumn;
    sortDirection: FileExplorerListingSortDirection;
    entryType: FileExplorerListingEntryType;
    signal?: AbortSignal;
}

interface FileExplorerListingLocateOptions {
    sortColumn: FileExplorerListingSortColumn;
    sortDirection: FileExplorerListingSortDirection;
    entryType: FileExplorerListingEntryType;
    signal?: AbortSignal;
}

export type { FileExplorerListingAcceptedResponse, FileExplorerListingEntryType, FileExplorerListingLocateOptions, FileExplorerListingLocateResponse, FileExplorerListingPageOptions, FileExplorerListingPageResponse, FileExplorerListingReleasedResponse, FileExplorerListingSortColumn, FileExplorerListingSortDirection };
