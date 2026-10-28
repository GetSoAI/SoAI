/* SoAI - Shared frontend API contract boundary file explorer listing contracts [frontend/assets/ts/core/api/contracts/fileExplorerListingContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerListingAcceptedResponse, FileExplorerListingLocateOptions, FileExplorerListingLocateResponse, FileExplorerListingPageOptions, FileExplorerListingPageResponse, FileExplorerListingReleasedResponse } from '@core/api/contracts/fileExplorerListingContractTypes.ts';
import { decodeFileExplorerEntry } from '@core/api/contracts/fileExplorerEntryContract.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiQueryParameters } from '@core/api/types/request.ts';
import { readOffsetPaginationMetadata } from '@core/data/offsetPagination.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredPresentStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE = 'directory_listing_expired';

const serializeFileExplorerListingStartRequest = (listingId: string, path: string): JsonObject => ({
    'listing_id': listingId,
    path
});

const serializeFileExplorerListingPageQuery = (options: FileExplorerListingPageOptions): ApiQueryParameters => ({
    offset: options.offset,
    limit: options.limit,
    'sort_column': options.sortColumn,
    'sort_direction': options.sortDirection,
    'entry_type': options.entryType
});

const serializeFileExplorerListingLocateQuery = (name: string, options: FileExplorerListingLocateOptions): ApiQueryParameters => ({
    name,
    'sort_column': options.sortColumn,
    'sort_direction': options.sortDirection,
    'entry_type': options.entryType
});

const decodeFileExplorerListingAcceptedResponse = (value: ApiResponsePayload): FileExplorerListingAcceptedResponse => {
    const label = 'File explorer listing accepted response';
    const record = requireRecord(value, label);
    const status = readRequiredTrimmedString(record, 'status', `${label}.status`);
    if (status !== 'accepted') throw new TypeError(`${label}.status must be accepted.`);
    return {
        status,
        listingId: readRequiredTrimmedString(record, 'listing_id', `${label}.listing_id`),
        taskId: readRequiredTrimmedString(record, 'task_id', `${label}.task_id`),
        path: readRequiredPresentStringValue(record['path'], `${label}.path`)
    };
};

const decodeFileExplorerListingPageResponse = (value: ApiResponsePayload): FileExplorerListingPageResponse => {
    const label = 'File explorer listing page response';
    const record = requireRecord(value, label);
    const entriesValue = record['entries'];
    if (!Array.isArray(entriesValue)) throw new TypeError(`${label}.entries must be an array.`);
    const metadata = readOffsetPaginationMetadata(record, label);
    if (entriesValue.length > metadata.limit) throw new TypeError(`${label}.entries exceeds its declared limit.`);
    const total = readRequiredNonNegativeIntegerValue(record['total'], `${label}.total`);
    const expectedHasMore = metadata.offset + entriesValue.length < total;
    const expectedNextOffset = expectedHasMore ? metadata.offset + entriesValue.length : null;
    if (metadata.hasMore !== expectedHasMore || metadata.nextOffset !== expectedNextOffset) {
        throw new TypeError(`${label} has_more and next_offset must match its entries and total.`);
    }
    return {
        listingId: readRequiredTrimmedString(record, 'listing_id', `${label}.listing_id`),
        path: readRequiredPresentStringValue(record['path'], `${label}.path`),
        entries: entriesValue.map((entry, index) => decodeFileExplorerEntry(entry, `${label}.entries[${String(index)}]`)),
        total,
        offset: metadata.offset,
        limit: metadata.limit,
        hasMore: metadata.hasMore,
        nextOffset: metadata.nextOffset,
        workspacePathResolved: readRequiredPresentStringValue(record['workspace_path_resolved'], `${label}.workspace_path_resolved`)
    };
};

const decodeFileExplorerListingLocateResponse = (value: ApiResponsePayload): FileExplorerListingLocateResponse => {
    const label = 'File explorer listing locate response';
    const record = requireRecord(value, label);
    return { offset: readRequiredNonNegativeIntegerValue(record['offset'], `${label}.offset`) };
};

const decodeFileExplorerListingReleasedResponse = (value: ApiResponsePayload): FileExplorerListingReleasedResponse => {
    const label = 'File explorer listing released response';
    const record = requireRecord(value, label);
    const status = readRequiredTrimmedString(record, 'status', `${label}.status`);
    if (status !== 'released') throw new TypeError(`${label}.status must be released.`);
    return {
        status,
        listingId: readRequiredTrimmedString(record, 'listing_id', `${label}.listing_id`)
    };
};

export { FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE, decodeFileExplorerListingAcceptedResponse, decodeFileExplorerListingLocateResponse, decodeFileExplorerListingPageResponse, decodeFileExplorerListingReleasedResponse, serializeFileExplorerListingLocateQuery, serializeFileExplorerListingPageQuery, serializeFileExplorerListingStartRequest };
