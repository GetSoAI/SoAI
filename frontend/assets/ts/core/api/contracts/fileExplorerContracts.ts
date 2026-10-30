/* SoAI - Shared frontend API contract boundary file explorer contracts [frontend/assets/ts/core/api/contracts/fileExplorerContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeFileExplorerEntry } from '@core/api/contracts/fileExplorerEntryContract.ts';
import { decodeFileExplorerListingAcceptedResponse, decodeFileExplorerListingLocateResponse, decodeFileExplorerListingPageResponse, decodeFileExplorerListingReleasedResponse } from '@core/api/contracts/fileExplorerListingContracts.ts';
import type { FileExplorerBatchItemResponse, FileExplorerBatchMetadataItemResponse, FileExplorerBatchMetadataResponse, FileExplorerBatchResponse, FileExplorerBatchUploadItemResponse, FileExplorerBatchUploadResponse, FileExplorerEntryResponse, FileExplorerListResponse, FileExplorerMetadataResponse, FileExplorerMoveMutationResponse, FileExplorerPathMutationResponse, FileExplorerReadResponse, FileExplorerSearchEntryResponse, FileExplorerSearchResponse, FileExplorerTaskAcceptedResponse, FileExplorerUploadResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readNullableNonNegativeIntegerValue, readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredPresentStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

const requireStatus = <Status extends string>(record: JsonObject, expected: Status, label: string): Status => {
    const status = readRequiredTrimmedString(record, 'status', `${label}.status`);
    if (status !== expected) {
        throw new TypeError(`${label}.status must be ${expected}.`);
    }
    return expected;
};

const requireString = (value: JsonValue | undefined, label: string): string => {
    if (!isString(value)) throw new TypeError(`${label} must be a string.`);
    return value;
};

const decodeEntries = (value: JsonValue | undefined, label: string): FileExplorerEntryResponse[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    return value.map((entry, index) => decodeFileExplorerEntry(entry, `${label}[${String(index)}]`));
};

const decodeSearchEntries = (value: JsonValue | undefined, label: string): FileExplorerSearchEntryResponse[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    return value.map((entry, index) => {
        const entryLabel = `${label}[${String(index)}]`;
        const record = requireRecord(entry, entryLabel);
        return {
            ...decodeFileExplorerEntry(entry, entryLabel),
            path: readRequiredPresentStringValue(record['path'], `${entryLabel}.path`)
        };
    });
};

const decodeMetadataRecord = <Value>(value: Value, label: string): FileExplorerMetadataResponse => {
    const record = requireRecord(value, label);
    return {
        ...decodeFileExplorerEntry(record, label),
        path: readRequiredPresentStringValue(record['path'], `${label}.path`),
        sha256: readNullableTrimmedStringValue(record['sha256'], `${label}.sha256`)
    };
};

const decodeFileExplorerListResponse = (value: ApiResponsePayload): FileExplorerListResponse => {
    const label = 'File explorer list response';
    const record = requireRecord(value, label);
    return {
        path: readRequiredPresentStringValue(record['path'], `${label}.path`),
        entries: decodeEntries(record['entries'], `${label}.entries`),
        total: readRequiredNonNegativeIntegerValue(record['total'], `${label}.total`),
        offset: readRequiredNonNegativeIntegerValue(record['offset'], `${label}.offset`),
        limit: readRequiredNonNegativeIntegerValue(record['limit'], `${label}.limit`),
        workspacePathResolved: readRequiredPresentStringValue(record['workspace_path_resolved'], `${label}.workspace_path_resolved`)
    };
};

const decodeFileExplorerSearchResponse = (value: ApiResponsePayload): FileExplorerSearchResponse => {
    const label = 'File explorer search response';
    const record = requireRecord(value, label);
    return {
        query: readRequiredTrimmedString(record, 'query', `${label}.query`),
        searchRoot: readRequiredPresentStringValue(record['search_root'], `${label}.search_root`),
        entries: decodeSearchEntries(record['entries'], `${label}.entries`),
        total: readRequiredNonNegativeIntegerValue(record['total'], `${label}.total`),
        offset: readRequiredNonNegativeIntegerValue(record['offset'], `${label}.offset`),
        limit: readRequiredNonNegativeIntegerValue(record['limit'], `${label}.limit`),
        truncated: readRequiredBooleanValue(record['truncated'], `${label}.truncated`),
        scannedEntries: readRequiredNonNegativeIntegerValue(record['scanned_entries'], `${label}.scanned_entries`),
        workspacePathResolved: readRequiredPresentStringValue(record['workspace_path_resolved'], `${label}.workspace_path_resolved`)
    };
};

const decodeFileExplorerBrowseResponse = (value: ApiResponsePayload, hasQuery: boolean): FileExplorerListResponse | FileExplorerSearchResponse => (hasQuery ? decodeFileExplorerSearchResponse(value) : decodeFileExplorerListResponse(value));

const decodeFileExplorerMetadataResponse = (value: ApiResponsePayload): FileExplorerMetadataResponse => decodeMetadataRecord(value, 'File explorer metadata response');

const decodeFileExplorerReadResponse = (value: ApiResponsePayload): FileExplorerReadResponse => {
    const label = 'File explorer read response';
    const record = requireRecord(value, label);
    return { path: readRequiredPresentStringValue(record['path'], `${label}.path`), content: requireString(record['content'], `${label}.content`) };
};

const decodeBatchItem = (value: JsonValue, label: string): FileExplorerBatchItemResponse => {
    const record = requireRecord(value, label);
    return { path: readRequiredPresentStringValue(record['path'], `${label}.path`), success: readRequiredBooleanValue(record['success'], `${label}.success`), error: readNullableTrimmedStringValue(record['error'], `${label}.error`) };
};

const decodeBatchItems = (value: JsonValue | undefined, label: string): FileExplorerBatchItemResponse[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    return value.map((entry, index) => decodeBatchItem(entry, `${label}[${String(index)}]`));
};

const decodeFileExplorerBatchResponse = (value: ApiResponsePayload): FileExplorerBatchResponse => {
    const label = 'File explorer batch response';
    const record = requireRecord(value, label);
    const response: FileExplorerBatchResponse = { status: requireStatus(record, 'ok', label), total: readRequiredNonNegativeIntegerValue(record['total'], `${label}.total`), succeeded: readRequiredNonNegativeIntegerValue(record['succeeded'], `${label}.succeeded`), failed: readRequiredNonNegativeIntegerValue(record['failed'], `${label}.failed`), results: decodeBatchItems(record['results'], `${label}.results`) };
    const destinationValue = record['destination'];
    const destination = destinationValue === null || destinationValue === undefined ? null : readRequiredPresentStringValue(destinationValue, `${label}.destination`);
    if (destination !== null) response.destination = destination;
    return response;
};

const decodeFileExplorerBatchMetadataResponse = (value: ApiResponsePayload): FileExplorerBatchMetadataResponse => {
    const label = 'File explorer batch metadata response';
    const record = requireRecord(value, label);
    const resultsValue = record['results'];
    if (!Array.isArray(resultsValue)) throw new TypeError(`${label}.results must be an array.`);
    const results = resultsValue.map((entry, index): FileExplorerBatchMetadataItemResponse => {
        const itemLabel = `${label}.results[${String(index)}]`;
        const item = requireRecord(entry, itemLabel);
        return {
            path: readRequiredPresentStringValue(item['path'], `${itemLabel}.path`),
            success: readRequiredBooleanValue(item['success'], `${itemLabel}.success`),
            metadata: item['metadata'] === null ? null : decodeMetadataRecord(item['metadata'], `${itemLabel}.metadata`),
            error: readNullableTrimmedStringValue(item['error'], `${itemLabel}.error`)
        };
    });
    return { status: requireStatus(record, 'ok', label), total: readRequiredNonNegativeIntegerValue(record['total'], `${label}.total`), succeeded: readRequiredNonNegativeIntegerValue(record['succeeded'], `${label}.succeeded`), failed: readRequiredNonNegativeIntegerValue(record['failed'], `${label}.failed`), results };
};

const decodeFileExplorerUploadResponse = (value: ApiResponsePayload): FileExplorerUploadResponse => {
    const label = 'File explorer upload response';
    const record = requireRecord(value, label);
    return { status: requireStatus(record, 'ok', label), path: readRequiredPresentStringValue(record['path'], `${label}.path`), size: readRequiredNonNegativeIntegerValue(record['size'], `${label}.size`), taskId: readRequiredTrimmedString(record, 'task_id', `${label}.task_id`) };
};

const decodeFileExplorerBatchUploadResponse = (value: ApiResponsePayload): FileExplorerBatchUploadResponse => {
    const label = 'File explorer batch upload response';
    const record = requireRecord(value, label);
    const resultsValue = record['results'];
    if (!Array.isArray(resultsValue)) throw new TypeError(`${label}.results must be an array.`);
    const results = resultsValue.map((entry, index): FileExplorerBatchUploadItemResponse => {
        const itemLabel = `${label}.results[${String(index)}]`;
        const item = requireRecord(entry, itemLabel);
        const result: FileExplorerBatchUploadItemResponse = { path: readRequiredPresentStringValue(item['path'], `${itemLabel}.path`), success: readRequiredBooleanValue(item['success'], `${itemLabel}.success`) };
        const size = readNullableNonNegativeIntegerValue(item['size'], `${itemLabel}.size`);
        const error = readNullableTrimmedStringValue(item['error'], `${itemLabel}.error`);
        const code = readNullableTrimmedStringValue(item['code'], `${itemLabel}.code`);
        if (code !== null) result.code = code;
        if (size !== null) result.size = size;
        if (error !== null) result.error = error;
        return result;
    });
    const total = readRequiredNonNegativeIntegerValue(record['total'], `${label}.total`);
    const succeeded = readRequiredNonNegativeIntegerValue(record['succeeded'], `${label}.succeeded`);
    const failed = readRequiredNonNegativeIntegerValue(record['failed'], `${label}.failed`);
    const successfulResults = results.filter((result) => result.success).length;
    if (results.length !== total || succeeded + failed !== total || successfulResults !== succeeded) {
        throw new TypeError(`${label} counts must match its per-file results.`);
    }
    return { status: requireStatus(record, 'ok', label), taskId: readRequiredTrimmedString(record, 'task_id', `${label}.task_id`), total, succeeded, failed, totalSize: readRequiredNonNegativeIntegerValue(record['total_size'], `${label}.total_size`), results };
};

const decodeFileExplorerPathMutationResponse = (value: ApiResponsePayload): FileExplorerPathMutationResponse => {
    const label = 'File explorer path mutation response';
    const record = requireRecord(value, label);
    return { status: requireStatus(record, 'ok', label), path: readRequiredPresentStringValue(record['path'], `${label}.path`) };
};

const decodeFileExplorerMoveMutationResponse = (value: ApiResponsePayload): FileExplorerMoveMutationResponse => {
    const label = 'File explorer move mutation response';
    const record = requireRecord(value, label);
    return { status: requireStatus(record, 'ok', label), source: readRequiredPresentStringValue(record['source'], `${label}.source`), destination: readRequiredPresentStringValue(record['destination'], `${label}.destination`) };
};

const decodeFileExplorerTaskAcceptedResponse = (value: ApiResponsePayload): FileExplorerTaskAcceptedResponse => {
    const label = 'File explorer task response';
    const record = requireRecord(value, label);
    return { status: requireStatus(record, 'accepted', label), taskId: readRequiredTrimmedString(record, 'task_id', `${label}.task_id`) };
};

const serializeFileExplorerPathsRequest = (paths: string[]): JsonObject => ({ paths });
const serializeFileExplorerPathRequest = (path: string): JsonObject => ({ path });
const serializeFileExplorerMoveRequest = (source: string, destination: string): JsonObject => ({ source, destination });
const serializeFileExplorerBatchMoveRequest = (sources: string[], destinationDir: string): JsonObject => ({ sources, 'destination_dir': destinationDir });

export { decodeFileExplorerBatchMetadataResponse, decodeFileExplorerBatchResponse, decodeFileExplorerBatchUploadResponse, decodeFileExplorerBrowseResponse, decodeFileExplorerListResponse, decodeFileExplorerListingAcceptedResponse, decodeFileExplorerListingLocateResponse, decodeFileExplorerListingPageResponse, decodeFileExplorerListingReleasedResponse, decodeFileExplorerMetadataResponse, decodeFileExplorerMoveMutationResponse, decodeFileExplorerPathMutationResponse, decodeFileExplorerReadResponse, decodeFileExplorerSearchResponse, decodeFileExplorerTaskAcceptedResponse, decodeFileExplorerUploadResponse, serializeFileExplorerBatchMoveRequest, serializeFileExplorerMoveRequest, serializeFileExplorerPathRequest, serializeFileExplorerPathsRequest };
