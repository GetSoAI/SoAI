/* SoAI - Frontend wallpaper API contracts [frontend/assets/ts/core/api/contracts/wallpaperContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import { readNullableNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';

interface WallpaperMetadataResponse {
    type: string | null;
    sizeBytes: number | null;
    width: number | null;
    height: number | null;
}

interface WallpaperInfoResponse {
    exists: boolean;
    url: string | null;
    metadata: WallpaperMetadataResponse | null;
}

interface WallpaperUploadResponse {
    message: string;
    taskId: string;
}

interface WallpaperDownloadResponse {
    message: string;
}

const decodeWallpaperMetadata = (value: ApiResponsePayload): WallpaperMetadataResponse | null => {
    if (value === null || value === undefined) return null;
    const record = requireRecord(value, 'Wallpaper response.metadata');
    return {
        type: readNullableTrimmedStringValue(record['type'], 'Wallpaper response.metadata.type'),
        sizeBytes: readNullableNonNegativeIntegerValue(record['size_bytes'], 'Wallpaper response.metadata.size_bytes'),
        width: readNullableNonNegativeIntegerValue(record['width'], 'Wallpaper response.metadata.width'),
        height: readNullableNonNegativeIntegerValue(record['height'], 'Wallpaper response.metadata.height')
    };
};

const decodeWallpaperInfoResponse = (value: ApiResponsePayload): WallpaperInfoResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, 'Wallpaper response'), 'Wallpaper response');
    return {
        exists: readRequiredBooleanValue(record['exists'], 'Wallpaper response.exists'),
        url: readNullableTrimmedStringValue(record['url'], 'Wallpaper response.url'),
        metadata: decodeWallpaperMetadata(record['metadata'])
    };
};

const decodeWallpaperUploadResponse = (value: ApiResponsePayload): WallpaperUploadResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, 'Wallpaper upload response'), 'Wallpaper upload response');
    return {
        message: readRequiredTrimmedString(record, 'message', 'Wallpaper upload response.message'),
        taskId: readRequiredTrimmedString(record, 'task_id', 'Wallpaper upload response.task_id')
    };
};

const decodeWallpaperDownloadResponse = (value: ApiResponsePayload): WallpaperDownloadResponse => {
    const record = requireRecord(requireJsonResponsePayload(value, 'Wallpaper download response'), 'Wallpaper download response');
    return { message: readRequiredTrimmedString(record, 'message', 'Wallpaper download response.message') };
};

export { decodeWallpaperDownloadResponse, decodeWallpaperInfoResponse, decodeWallpaperUploadResponse };
export type { WallpaperDownloadResponse, WallpaperInfoResponse, WallpaperMetadataResponse, WallpaperUploadResponse };
