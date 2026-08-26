/* SoAI - Shared frontend connection status health [frontend/assets/ts/core/connectionstatus/health.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RestartInfo, SnapshotMeta, SystemInfo } from '@core/connectionstatus/types.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isArray, isBoolean, isNumber, isObject, isString } from '@core/typeGuards.ts';

const createDefaultRestartInfo = (): RestartInfo => ({
    required: false,
    timestamp: null,
    pid: null,
    reasons: [],
    notifications: []
});

const readSnapshotMeta = (snapshot: JsonValue | undefined): SnapshotMeta | null => {
    if (!isObject(snapshot)) return null;

    const metaValue = snapshot['meta'];
    const metadataValue = snapshot['metadata'];
    const detailValue = snapshot['detail'];
    const valueValue = snapshot['value'];

    const pickMeta = (candidate: JsonValue | undefined): SnapshotMeta | null => {
        if (!isObject(candidate)) return null;
        const cachedValue = candidate['cached'];
        const sourceValue = candidate['source'];
        const originValue = candidate['origin'];

        const meta: SnapshotMeta = {
            cached: isBoolean(cachedValue) ? cachedValue : null,
            source: isString(sourceValue) ? sourceValue : null,
            origin: isString(originValue) ? originValue : null
        };

        if (meta.cached !== null || meta.source !== null || meta.origin !== null) return meta;
        return null;
    };

    return pickMeta(metaValue) || pickMeta(metadataValue) || readSnapshotMeta(detailValue) || readSnapshotMeta(valueValue);
};

const normalizeStatusPayload = (payload: JsonValue | undefined): JsonObject | null => {
    if (!isObject(payload)) return null;

    if (hasOwn(payload, 'payload')) {
        const nested = payload['payload'];
        const fromNested = normalizeStatusPayload(nested);
        if (fromNested) return fromNested;
    }

    if (hasOwn(payload, 'value')) {
        const nested = payload['value'];
        const fromNested = normalizeStatusPayload(nested);
        if (fromNested) return fromNested;
    }

    const statusValue = payload['status'];
    if (isJsonObject(statusValue)) return statusValue;

    return isJsonObject(payload) ? payload : null;
};

const mergeStatus = (current: JsonObject | null, update: JsonObject): JsonObject => ({ ...(current ?? {}), ...update });

const extractSystemState = (payload: JsonValue | undefined): JsonObject | null => {
    if (!isJsonObject(payload)) return null;

    const direct = payload['systemState'];
    if (isJsonObject(direct)) return direct;

    const nestedKeys: readonly ('payload' | 'value' | 'detail')[] = ['payload', 'value', 'detail'];
    for (const key of nestedKeys) {
        const nested = payload[key];
        if (isJsonObject(nested)) {
            const found = extractSystemState(nested);
            if (found) return found;
        }
    }
    return null;
};

const hasSystemStateKey = (payload: JsonValue | undefined): boolean => {
    if (!isJsonObject(payload)) return false;
    if (hasOwn(payload, 'systemState')) return true;

    const nestedKeys: readonly ('payload' | 'value' | 'detail')[] = ['payload', 'value', 'detail'];
    for (const key of nestedKeys) {
        const nested = payload[key];
        if (isJsonObject(nested) && hasSystemStateKey(nested)) return true;
    }
    return false;
};

const normalizeRestartInfo = (systemState: JsonObject): RestartInfo => {
    const requiredValue = systemState['required'];
    if (!isBoolean(requiredValue)) throw new Error('Restart info missing required flag');

    const reasonsValue = systemState['reasons'];
    if (!isArray(reasonsValue)) throw new Error('Restart info reasons must be an array');

    const notificationsValue = systemState['notifications'];
    if (!isArray(notificationsValue)) throw new Error('Restart info notifications must be an array');

    const reasons: string[] = [];
    for (const entry of reasonsValue) {
        if (!isString(entry)) throw new Error('Restart info reason must be a string');
        const trimmed = entry.trim();
        if (trimmed) reasons.push(trimmed);
    }

    const notifications: RestartInfo['notifications'] = [];
    for (const entry of notificationsValue) {
        if (!isJsonObject(entry)) throw new Error('Restart info notification must be an object');
        const reasonValue = entry['reason'];
        if (!isString(reasonValue)) throw new Error('Restart info notification reason must be a string');
        const reason = reasonValue.trim();
        if (!reason) throw new Error('Restart info notification reason must be a non-empty string');

        const pathValue = entry['path'];
        const path = isString(pathValue) && pathValue.trim() ? pathValue.trim() : null;

        const timestampValue = entry['timestamp'];
        const timestamp = isNumber(timestampValue) && Number.isFinite(timestampValue) ? timestampValue : null;

        notifications.push({ reason, path, timestamp });
    }

    const timestampValue = systemState['timestamp'];
    const pidValue = systemState['pid'];

    return {
        required: requiredValue,
        timestamp: isNumber(timestampValue) && Number.isFinite(timestampValue) ? timestampValue : null,
        pid: isNumber(pidValue) && Number.isFinite(pidValue) ? pidValue : null,
        reasons,
        notifications
    };
};

const areRestartInfosEqual = (leftRestartInfo: RestartInfo, rightRestartInfo: RestartInfo): boolean => {
    if (leftRestartInfo === rightRestartInfo) return true;
    if (leftRestartInfo.required !== rightRestartInfo.required || leftRestartInfo.timestamp !== rightRestartInfo.timestamp || leftRestartInfo.pid !== rightRestartInfo.pid || leftRestartInfo.reasons.length !== rightRestartInfo.reasons.length || leftRestartInfo.notifications.length !== rightRestartInfo.notifications.length) return false;

    for (let entryIndex = 0; entryIndex < leftRestartInfo.reasons.length; entryIndex += 1) {
        const leftReason = leftRestartInfo.reasons[entryIndex];
        const rightReason = rightRestartInfo.reasons[entryIndex];
        if (leftReason === undefined || rightReason === undefined) return false;
        if (leftReason !== rightReason) return false;
    }

    for (let entryIndex = 0; entryIndex < leftRestartInfo.notifications.length; entryIndex += 1) {
        const leftNotification = leftRestartInfo.notifications[entryIndex];
        const rightNotification = rightRestartInfo.notifications[entryIndex];
        if (!leftNotification || !rightNotification) return false;
        if (leftNotification.reason !== rightNotification.reason) return false;
        if ((leftNotification.path ?? null) !== (rightNotification.path ?? null)) return false;
        if ((leftNotification.timestamp ?? null) !== (rightNotification.timestamp ?? null)) return false;
    }

    return true;
};

const extractSystemInfo = (rawPayload: JsonValue | undefined, normalized: JsonObject | null): SystemInfo => {
    const sources: JsonObject[] = [];

    const push = (candidate: JsonValue | undefined): void => {
        if (isJsonObject(candidate)) sources.push(candidate);
    };

    push(normalized);
    push(rawPayload);
    if (isJsonObject(rawPayload)) {
        push(rawPayload['system_info']);
    }

    const pick = (keys: readonly string[]): JsonValue | undefined => {
        for (const source of sources) {
            for (const key of keys) {
                if (!hasOwn(source, key)) continue;
                const value = source[key];
                if (value !== undefined && value !== null && value !== '') return value;
            }
        }
        return undefined;
    };

    const pickString = (keys: readonly string[]): string | null => {
        const value = pick(keys);
        if (!isString(value)) return null;
        const trimmed = value.trim();
        return trimmed ? trimmed : null;
    };

    const pickNumber = (keys: readonly string[], parser: (value: string) => number): number | null => {
        const value = pick(keys);
        if (isNumber(value) && Number.isFinite(value)) return value;
        if (isString(value)) {
            const parsed = parser(value);
            if (Number.isFinite(parsed)) return parsed;
        }
        return null;
    };

    const uptime = pickNumber(['uptime'], (stringValue) => parseFloat(stringValue));
    const port = pickNumber(['port'], (stringValue) => parseInt(stringValue, 10));

    return {
        name: pickString(['name', 'system_name']),
        soaiVersion: pickString(['soaiVersion', 'soai_version']),
        build: pickString(['build']),
        platform: pickString(['platform']),
        pythonVersion: pickString(['pythonVersion', 'python_version']),
        uptime,
        port
    };
};

export { createDefaultRestartInfo, readSnapshotMeta, normalizeStatusPayload, mergeStatus, extractSystemState, hasSystemStateKey, normalizeRestartInfo, areRestartInfosEqual, extractSystemInfo };
