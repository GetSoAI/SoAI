/* SoAI - Directory snapshot transport contracts [frontend/assets/ts/core/fileexplorerbrowser/directoryListingContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerListingAcceptedResponse, FileExplorerListingLocateOptions, FileExplorerListingLocateResponse, FileExplorerListingPageOptions, FileExplorerListingPageResponse, FileExplorerListingReleasedResponse } from '@core/api/contracts/fileExplorerListingContractTypes.ts';
import type { FileBrowserEntry } from '@core/fileexplorerbrowser/types.ts';
import type { FileExplorerSearchResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';

type DirectoryListingReleaseRecovery = (recover: () => void, authEnded: () => void, failure: Error, listingId: string) => () => void;

interface DirectoryListingApi {
    startListing(listingId: string, path: string, signal?: AbortSignal): Promise<FileExplorerListingAcceptedResponse>;
    getListingPage(listingId: string, options: FileExplorerListingPageOptions): Promise<FileExplorerListingPageResponse>;
    locateListingEntry(listingId: string, name: string, options: FileExplorerListingLocateOptions): Promise<FileExplorerListingLocateResponse>;
    releaseListing(listingId: string, signal?: AbortSignal): Promise<FileExplorerListingReleasedResponse>;
    search(options: { path: string; query: string; limit: number; includeTotal: boolean; signal: AbortSignal }): Promise<FileExplorerSearchResponse>;
}

interface DirectoryListingSnapshot {
    readonly updatedAtMs: number;
    readonly currentPath: string;
    readonly workspacePathResolved: string;
    readonly entries: readonly FileBrowserEntry[];
    readonly total: number;
    readonly hasMore: boolean;
    readonly nextOffset: number | null;
}

interface DirectoryListingSelection {
    readonly paths: readonly string[];
    readonly removeMissing: (paths: readonly string[]) => void;
}

export type { DirectoryListingReleaseRecovery, DirectoryListingApi, DirectoryListingSnapshot, DirectoryListingSelection };
