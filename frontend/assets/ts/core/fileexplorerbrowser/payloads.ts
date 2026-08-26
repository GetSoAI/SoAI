/* SoAI - Shared file explorer browser payloads [frontend/assets/ts/core/fileexplorerbrowser/payloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerListResponse, FileExplorerMetadataResponse, FileExplorerReadResponse } from '@core/api/contracts/fileExplorerContractTypes.ts';
import { formatDateTime } from '@core/primitives/dateTime.ts';
import { parseFileBrowserEntriesPayload } from '@core/fileexplorerbrowser/parsing.ts';
import { toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import type { FileBrowserListPayload, FileBrowserMetadata, FileBrowserReadPayload } from '@core/fileexplorerbrowser/types.ts';

const parseFileBrowserMetadataPayload = (record: FileExplorerMetadataResponse): FileBrowserMetadata => {
    return {
        path: toVirtualPath(record.path),
        name: record.name,
        isDirectory: record.isDirectory,
        size: record.size,
        modifiedAt: formatDateTime(record.modifiedAtMs, true),
        mimeType: record.mimeType,
        typeId: record.typeId,
        typeRank: record.typeRank,
        permissions: record.permissions,
        sha256: record.sha256
    };
};

const parseFileBrowserReadPayload = (record: FileExplorerReadResponse): FileBrowserReadPayload => {
    return {
        path: toVirtualPath(record.path),
        content: record.content
    };
};

const parseFileBrowserListPayload = (record: FileExplorerListResponse): FileBrowserListPayload => {
    const path = toVirtualPath(record.path);
    return {
        path,
        entries: parseFileBrowserEntriesPayload(record, path, false),
        total: record.total,
        offset: record.offset,
        limit: record.limit
    };
};

export { parseFileBrowserListPayload, parseFileBrowserMetadataPayload, parseFileBrowserReadPayload };
