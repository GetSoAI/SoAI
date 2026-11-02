/* SoAI - Typed listing reconciliation and snapshot integrity failures [frontend/assets/ts/core/fileexplorerbrowser/directoryListingFailure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE } from '@core/api/contracts/fileExplorerListingContracts.ts';
import { extractErrorCode, isErrorHttpStatus } from '@core/errors/coerce.ts';
import type { DirectoryListingBrowserState } from '@core/fileexplorerbrowser/types.ts';

class DirectoryListingFailure extends Error {
    readonly reason: 'changed' | 'timeout' | 'incoherent';

    constructor(reason: 'changed' | 'timeout' | 'incoherent', diagnostic: string) {
        super(diagnostic);
        this.name = 'DirectoryListingFailure';
        this.reason = reason;
    }
}

const resolveDirectoryListingFailureFreshness = (error: Error, previous: DirectoryListingBrowserState['freshness']): 'stale' | 'unavailable' => {
    if (previous === 'unavailable' || (error instanceof DirectoryListingFailure && error.reason === 'incoherent') || isErrorHttpStatus(error, 403) || (isErrorHttpStatus(error, 404) && extractErrorCode(error) !== FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE)) return 'unavailable';
    return 'stale';
};

export { DirectoryListingFailure, resolveDirectoryListingFailureFreshness };
