/* SoAI - Backend update advisory decoding and action policy [frontend/assets/ts/core/plugins/backendUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PluginBackendUpdateAdvisory, PluginRecord } from '@core/types/pluginTypes.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue } from '@core/types/payloadValueReaders.ts';

interface BackendUpdateAccess {
    canAdminister: boolean;
    online: boolean;
    restartPending: boolean;
    catalogFresh: boolean;
    operationActive: boolean;
}

const decodePluginBackendUpdate = <T>(value: T): PluginBackendUpdateAdvisory => {
    const record = requireRecord(value, 'backend_update');
    for (const key of ['status', 'current_version', 'latest_version', 'checked_at_ms', 'auto_update_failed', 'can_update']) {
        if (record[key] === undefined) throw new TypeError(`backend_update.${key} is required`);
    }
    const status = record['status'];
    if (status !== 'none' && status !== 'check_pending' && status !== 'current' && status !== 'update_available' && status !== 'check_failed' && status !== 'unavailable') {
        throw new TypeError('backend_update.status is invalid');
    }
    const checkedAtMs = readNullableNonNegativeIntegerValue(record['checked_at_ms'], 'backend_update.checked_at_ms');
    if (checkedAtMs !== null && !Number.isSafeInteger(checkedAtMs)) throw new TypeError('backend_update.checked_at_ms is outside the supported range');
    if ((status === 'current' || status === 'update_available') && checkedAtMs === null) throw new TypeError('A successful backend update check requires a timestamp');
    return {
        status,
        currentVersion: readNullableTrimmedStringValue(record['current_version'], 'backend_update.current_version'),
        latestVersion: readNullableTrimmedStringValue(record['latest_version'], 'backend_update.latest_version'),
        checkedAtMs,
        autoUpdateFailed: readRequiredBooleanValue(record['auto_update_failed'], 'backend_update.auto_update_failed'),
        canUpdate: readRequiredBooleanValue(record['can_update'], 'backend_update.can_update')
    };
};

const hasPluginBackendUpdate = (plugin: PluginRecord): boolean => plugin.backendUpdate?.status === 'update_available';

const canCheckPluginBackend = (access: BackendUpdateAccess): boolean => access.canAdminister && access.online && !access.restartPending && access.catalogFresh && !access.operationActive;

const canUpdatePluginBackend = (plugin: PluginRecord, access: BackendUpdateAccess): boolean => (plugin.backendUpdate === undefined ? plugin.capabilities?.supportsBackendInstallation === true : plugin.backendUpdate.canUpdate) && canCheckPluginBackend(access);

export { canCheckPluginBackend, canUpdatePluginBackend, decodePluginBackendUpdate, hasPluginBackendUpdate };
export type { BackendUpdateAccess };
