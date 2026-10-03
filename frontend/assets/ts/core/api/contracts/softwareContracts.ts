/* SoAI - Shared frontend API contract boundary software contracts [frontend/assets/ts/core/api/contracts/softwareContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';

interface SoftwareReleaseHistoryEntry {
    version: string;
    body: string;
    publishedAt: string | null;
}

interface SoftwareUpdateCheckResponse {
    updateAvailable: boolean;
    currentVersion: string | null;
    latestVersion: string | null;
    message: string | null;
    releaseUrl: string | null;
    publishedAt: string | null;
    releaseNotes: string | null;
    releaseHistory?: SoftwareReleaseHistoryEntry[];
    releaseHistoryComplete?: boolean;
    platformId: string | null;
    deliveryType: SoftwareUpdateDeliveryType;
    installSupported: boolean;
}

interface SoftwareUpdateAcceptedResponse {
    status: 'accepted';
    message: string;
    platformId: string;
    deliveryType: Exclude<SoftwareUpdateDeliveryType, null>;
}

type SoftwareUpdatePreparationPhase = 'preparing' | 'fetching' | 'verifying' | 'downloading' | 'staging' | 'handoff' | 'unavailable';

interface SoftwareUpdatePreparationResponse {
    active: boolean;
    taskId: string | null;
    phase: SoftwareUpdatePreparationPhase | null;
    downloadedBytes: number | null;
    totalBytes: number | null;
    updatedAtMs: number | null;
}

type SoftwareUpdateDeliveryType = 'complete_archive' | 'installer' | null;

interface SoftwareUpdateNotice {
    taskId: string;
    status: 'completed' | 'failed';
    fromVersion: string;
    toVersion: string;
    finishedAtMs: number;
}

const SOFTWARE_UPDATE_NOTICE_STATUSES: readonly ['completed', 'failed'] = Object.freeze(['completed', 'failed']);

const readPreparationPhase = (value: ApiResponsePayload): SoftwareUpdatePreparationPhase => {
    switch (value) {
        case 'preparing':
        case 'fetching':
        case 'verifying':
        case 'downloading':
        case 'staging':
        case 'handoff':
        case 'unavailable':
            return value;
        default:
            throw new TypeError('Software update preparation response.phase is invalid.');
    }
};

const readNullableSafeInteger = (value: ApiResponsePayload, label: string): number | null => {
    if (value === null || value === undefined) return null;
    if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
        throw new TypeError(`${label} must be a non-negative safe integer.`);
    }
    return value;
};

const readSoftwareUpdateDeliveryType = <T>(value: T, label: string): SoftwareUpdateDeliveryType => {
    if (value === null) {
        return null;
    }
    if (value === 'complete_archive') {
        return 'complete_archive';
    }
    if (value === 'installer') {
        return 'installer';
    }
    throw new TypeError(`${label} must be complete_archive, installer, or null.`);
};

const decodeSoftwareUpdateCheckResponse = (value: ApiResponsePayload): SoftwareUpdateCheckResponse => {
    const record = requireRecord(value, 'Software update check response');
    const updateAvailable = readRequiredBooleanValue(record['update_available'], 'Software update check response.update_available');
    const rawHistory = record['release_history'];
    if (rawHistory !== undefined && !Array.isArray(rawHistory)) {
        throw new TypeError('Software update check response.release_history must be an array.');
    }
    const releaseHistory = (rawHistory ?? []).map((entry) => {
        const release = requireRecord(entry, 'Software release history entry');
        return {
            version: readRequiredTrimmedString(release, 'version', 'Software release history entry.version'),
            body: readRequiredTrimmedString(release, 'body', 'Software release history entry.body'),
            publishedAt: readNullableTrimmedStringValue(release['published_at'], 'Software release history entry.published_at')
        };
    });
    const historyComplete = record['release_history_complete'];
    if (historyComplete !== undefined && typeof historyComplete !== 'boolean') {
        throw new TypeError('Software update check response.release_history_complete must be a boolean.');
    }
    return {
        updateAvailable,
        currentVersion: readNullableTrimmedStringValue(record['current_version'], 'Software update check response.current_version'),
        latestVersion: readNullableTrimmedStringValue(record['latest_version'], 'Software update check response.latest_version'),
        message: readNullableTrimmedStringValue(record['message'], 'Software update check response.message'),
        releaseUrl: readNullableTrimmedStringValue(record['release_url'], 'Software update check response.release_url'),
        publishedAt: readNullableTrimmedStringValue(record['published_at'], 'Software update check response.published_at'),
        releaseNotes: readNullableTrimmedStringValue(record['release_notes'], 'Software update check response.release_notes'),
        releaseHistory,
        releaseHistoryComplete: historyComplete ?? !updateAvailable,
        platformId: readNullableTrimmedStringValue(record['platform_id'], 'Software update check response.platform_id'),
        deliveryType: readSoftwareUpdateDeliveryType(record['delivery_type'], 'Software update check response.delivery_type'),
        installSupported: readRequiredBooleanValue(record['install_supported'], 'Software update check response.install_supported')
    };
};

const decodeSoftwareUpdatePreparationResponse = (value: ApiResponsePayload): SoftwareUpdatePreparationResponse => {
    const record = requireRecord(value, 'Software update preparation response');
    const active = readRequiredBooleanValue(record['active'], 'Software update preparation response.active');
    if (!active) {
        return { active: false, taskId: null, phase: null, downloadedBytes: null, totalBytes: null, updatedAtMs: null };
    }
    const phase = readPreparationPhase(record['phase']);
    const downloadedBytes = readNullableSafeInteger(record['downloaded_bytes'], 'Software update preparation response.downloaded_bytes');
    const totalBytes = readNullableSafeInteger(record['total_bytes'], 'Software update preparation response.total_bytes');
    const updatedAtMs = readNullableSafeInteger(record['updated_at_ms'], 'Software update preparation response.updated_at_ms');
    if (downloadedBytes !== null && (totalBytes === null || totalBytes <= 0 || downloadedBytes > totalBytes)) {
        throw new TypeError('Software update preparation response download progress is invalid.');
    }
    if (downloadedBytes === null && totalBytes !== null) {
        throw new TypeError('Software update preparation response download total is invalid.');
    }
    if (updatedAtMs !== null && updatedAtMs <= 0) {
        throw new TypeError('Software update preparation response timestamp is invalid.');
    }
    return {
        active: true,
        taskId: readRequiredTrimmedString(record, 'task_id', 'Software update preparation response.task_id'),
        phase,
        downloadedBytes,
        totalBytes,
        updatedAtMs
    };
};

const decodeSoftwareUpdateAcceptedResponse = (value: ApiResponsePayload): SoftwareUpdateAcceptedResponse => {
    const record = requireRecord(value, 'Software update response');
    const status = readRequiredTrimmedString(record, 'status', 'Software update response.status');
    if (status !== 'accepted') {
        throw new TypeError('Software update response.status must be accepted.');
    }
    const deliveryType = readSoftwareUpdateDeliveryType(record['delivery_type'], 'Software update response.delivery_type');
    if (deliveryType === null) {
        throw new TypeError('Software update response.delivery_type cannot be null.');
    }
    return {
        status,
        message: readRequiredTrimmedString(record, 'message', 'Software update response.message'),
        platformId: readRequiredTrimmedString(record, 'platform_id', 'Software update response.platform_id'),
        deliveryType
    };
};

const decodeSoftwareUpdateNoticeResponse = (value: ApiResponsePayload): SoftwareUpdateNotice | null => {
    const record = requireRecord(value, 'Software update notice response');
    assertExactRecordKeys(record, ['notice'], 'Software update notice response');
    if (record['notice'] === null) {
        return null;
    }
    const notice = requireRecord(record['notice'], 'Software update notice');
    assertExactRecordKeys(notice, ['task_id', 'status', 'from_version', 'to_version', 'finished_at_ms'], 'Software update notice');
    return {
        taskId: readRequiredTrimmedString(notice, 'task_id', 'Software update notice.task_id'),
        status: readRequiredEnumValue(notice['status'], 'Software update notice.status', SOFTWARE_UPDATE_NOTICE_STATUSES),
        fromVersion: readRequiredTrimmedString(notice, 'from_version', 'Software update notice.from_version'),
        toVersion: readRequiredTrimmedString(notice, 'to_version', 'Software update notice.to_version'),
        finishedAtMs: readRequiredNonNegativeIntegerValue(notice['finished_at_ms'], 'Software update notice.finished_at_ms')
    };
};

export { decodeSoftwareUpdateAcceptedResponse, decodeSoftwareUpdateCheckResponse, decodeSoftwareUpdateNoticeResponse, decodeSoftwareUpdatePreparationResponse };
export type { SoftwareReleaseHistoryEntry, SoftwareUpdateAcceptedResponse, SoftwareUpdateCheckResponse, SoftwareUpdateDeliveryType, SoftwareUpdateNotice, SoftwareUpdatePreparationResponse };
