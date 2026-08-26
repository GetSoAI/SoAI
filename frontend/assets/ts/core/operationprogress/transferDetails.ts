/* SoAI - Operation progress transfer detail formatting [frontend/assets/ts/core/operationprogress/transferDetails.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { isFiniteNumber, isObject } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

const DOWNLOADED_KEYS: readonly string[] = ['downloaded_size', 'downloaded_bytes', 'bytes_downloaded', 'bytes_done', 'transferred_bytes'];
const TOTAL_KEYS: readonly string[] = ['total_size', 'total_bytes', 'total_size_bytes', 'bytes_total'];
const SPEED_KEYS: readonly string[] = ['bytes_per_second', 'speed', 'download_speed'];
const ETA_KEYS: readonly string[] = ['eta_seconds', 'eta'];

const readFiniteNumberField = (payload: JsonObject, keys: readonly string[]): number | null => {
    for (const key of keys) {
        const value = payload[key];
        if (isFiniteNumber(value)) {
            return Math.max(0, value);
        }
        if (typeof value !== 'string') {
            continue;
        }
        const parsed = Number(value.trim());
        if (isFiniteNumber(parsed)) {
            return Math.max(0, parsed);
        }
    }
    return null;
};

const formatEta = (seconds: number | null): string => {
    if (!isFiniteNumber(seconds) || seconds <= 0) {
        return '';
    }
    if (seconds < 60) {
        return `${Math.floor(seconds)}s`;
    }
    if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
    }
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
};

const formatTransferSize = (downloadedBytes: number | null, totalBytes: number | null): string => {
    const downloaded = downloadedBytes !== null ? formatBytes(downloadedBytes, 1) : '';
    if (totalBytes !== null && totalBytes > 0) {
        return `${downloaded || formatBytes(0, 1)} / ${formatBytes(totalBytes, 1)}`;
    }
    return downloadedBytes !== null && downloadedBytes > 0 ? downloaded : '';
};

const resolveOperationProgressDetails = (payload: JsonValue | null | undefined): string => {
    if (!isObject(payload)) {
        return '';
    }
    const explicitDetails = toTrimmedString(payload['details']);
    if (explicitDetails) {
        return explicitDetails;
    }
    const downloadedBytes = readFiniteNumberField(payload, DOWNLOADED_KEYS);
    const totalBytes = readFiniteNumberField(payload, TOTAL_KEYS);
    const speed = readFiniteNumberField(payload, SPEED_KEYS);
    const etaSeconds = readFiniteNumberField(payload, ETA_KEYS);
    const parts = [
        formatTransferSize(downloadedBytes, totalBytes),
        speed !== null && speed > 0 ? `${formatBytes(speed, 1)}/s` : '',
        (() => {
            const eta = formatEta(etaSeconds);
            return eta ? `ETA ${eta}` : '';
        })()
    ].filter(Boolean);
    return parts.join(' | ');
};

export { resolveOperationProgressDetails };
