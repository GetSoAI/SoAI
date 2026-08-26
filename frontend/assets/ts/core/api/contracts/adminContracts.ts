/* SoAI - Shared frontend API contract boundary admin contracts [frontend/assets/ts/core/api/contracts/adminContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readNullableNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanRecordValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import { isString } from '@core/typeGuards.ts';

interface BackupListEntry {
    backupId: string;
    timestampMs: number | null;
    totalSizeBytes: number | null;
    targetsCompleted: Record<string, boolean>;
    licensingRecoveryState: 'not_applicable' | 'complete' | 'incomplete';
}

interface BackupListResponse {
    backups: BackupListEntry[];
}

interface BackupTaskAcceptedResponse {
    status: 'accepted';
    taskId: string;
}

interface FactoryResetResponse {
    message: string;
    purgedPathsManifest: string[];
}

const decodeBackupEntry = (value: ApiResponsePayload, label: string): BackupListEntry => {
    const record = requireRecord(value, label);
    const licensingRecoveryState = readRequiredTrimmedString(record, 'licensing_recovery_state', `${label}.licensing_recovery_state`);
    if (licensingRecoveryState !== 'not_applicable' && licensingRecoveryState !== 'complete' && licensingRecoveryState !== 'incomplete') {
        throw new TypeError(`${label}.licensing_recovery_state is invalid.`);
    }
    return {
        backupId: readRequiredTrimmedString(record, 'backup_id', `${label}.backup_id`),
        timestampMs: readNullableNonNegativeIntegerValue(record['timestamp_ms'], `${label}.timestamp_ms`),
        totalSizeBytes: readNullableNonNegativeIntegerValue(record['total_size_bytes'], `${label}.total_size_bytes`),
        targetsCompleted: readRequiredBooleanRecordValue(record['targets_completed'], `${label}.targets_completed`),
        licensingRecoveryState
    };
};

const decodeBackupListResponse = (value: ApiResponsePayload): BackupListResponse => {
    const record = requireRecord(value, 'Backup list response');
    const backups = record['backups'];
    if (!Array.isArray(backups)) {
        throw new TypeError('Backup list response.backups must be an array.');
    }
    return { backups: backups.map((backup, index) => decodeBackupEntry(backup, `Backup list response.backups[${String(index)}]`)) };
};

const decodeBackupTaskAcceptedResponse = (value: ApiResponsePayload): BackupTaskAcceptedResponse => {
    const record = requireRecord(value, 'Backup task response');
    const status = readRequiredTrimmedString(record, 'status', 'Backup task response.status');
    if (status !== 'accepted') {
        throw new TypeError('Backup task response.status must be accepted.');
    }
    return { status, taskId: readRequiredTrimmedString(record, 'task_id', 'Backup task response.task_id') };
};

const decodeFactoryResetResponse = (value: ApiResponsePayload): FactoryResetResponse => {
    const record = requireRecord(value, 'Factory reset response');
    const paths = record['purged_paths_manifest'];
    if (!Array.isArray(paths)) {
        throw new TypeError('Factory reset response.purged_paths_manifest must be an array.');
    }
    const purgedPathsManifest = paths.map((path, index) => {
        if (!isString(path) || !path.trim()) {
            throw new TypeError(`Factory reset response.purged_paths_manifest[${String(index)}] must be a non-empty string.`);
        }
        return path;
    });
    return { message: readRequiredTrimmedString(record, 'message', 'Factory reset response.message'), purgedPathsManifest };
};

const decodeBackupExportResponse = (value: ApiResponsePayload): Response => {
    if (!(value instanceof Response)) {
        throw new TypeError('Backup export response must be a Response.');
    }
    return value;
};

export { decodeBackupExportResponse, decodeBackupListResponse, decodeBackupTaskAcceptedResponse, decodeFactoryResetResponse };
export type { BackupListEntry, BackupListResponse, BackupTaskAcceptedResponse, FactoryResetResponse };
