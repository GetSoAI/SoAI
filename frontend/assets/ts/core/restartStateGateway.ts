/* SoAI - Shared frontend restart state gateway [frontend/assets/ts/core/restartStateGateway.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getStreamResources } from '@core/realtime/streammanager/public.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import { STATUS } from '@core/realtime/streammanager/resources/ids.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isBoolean, isFiniteNumber, isObject, isString, hasOwn } from '@core/typeGuards.ts';

interface RestartNotification {
    reason: string;
    path: string | null;
    timestamp: number | null;
}

interface RestartState {
    required: boolean;
    timestamp: number | null;
    pid: number | null;
    reasons: string[];
    notifications: RestartNotification[];
}

const getStatusStreamId = (): string => STATUS;

const normalizeReasons = (source: JsonValue | null | undefined): string[] => {
    if (!isArray(source)) {
        throw new Error('Restart state reasons must be an array');
    }
    return source
        .map((entry) => {
            if (!isString(entry)) {
                throw new Error('Restart state reason must be a string');
            }
            const trimmed = entry.trim();
            if (!trimmed) {
                throw new Error('Restart state reason must not be empty');
            }
            return trimmed;
        })
        .filter((entry) => entry.length);
};

const normalizeNotifications = (source: JsonValue | null | undefined): RestartNotification[] => {
    if (!isArray(source)) {
        throw new Error('Restart state notifications must be an array');
    }
    return source.map((entry) => {
        if (!isObject(entry)) {
            throw new Error('Restart state notification must be an object');
        }
        const rawEntry = entry;
        const reason = isString(rawEntry['reason']) ? rawEntry['reason'].trim() : '';
        if (!reason) {
            throw new Error('Restart state notification reason must be a non-empty string');
        }
        const path = isString(rawEntry['path']) && rawEntry['path'].trim().length ? rawEntry['path'].trim() : null;
        const timestamp = isFiniteNumber(rawEntry['timestamp']) ? Number(rawEntry['timestamp']) : null;
        return { reason, path, timestamp };
    });
};

const normalizeRestartState = (payload: JsonValue | null | undefined): RestartState => {
    if (!isObject(payload)) {
        throw new Error('Restart state payload must be an object');
    }
    const rawPayload = payload;
    if (!isBoolean(rawPayload['required'])) {
        throw new Error('Restart state payload missing required flag');
    }
    const timestamp = isFiniteNumber(rawPayload['timestamp']) ? Number(rawPayload['timestamp']) : null;
    const pid = isFiniteNumber(rawPayload['pid']) ? Number(rawPayload['pid']) : null;
    const reasons = normalizeReasons(rawPayload['reasons']);
    const notifications = normalizeNotifications(rawPayload['notifications']);
    return {
        required: rawPayload['required'],
        timestamp,
        pid,
        reasons,
        notifications
    };
};

const createEmptyRestartState = (): RestartState => ({
    required: false,
    timestamp: null,
    pid: null,
    reasons: [],
    notifications: []
});

const extractCanonicalState = (snapshot: JsonValue | null | undefined): RestartState => {
    if (!isObject(snapshot)) {
        throw new Error('Restart state snapshot must be an object');
    }
    if (!hasOwn(snapshot, 'systemState')) {
        throw new Error('Restart state snapshot missing systemState key');
    }
    return normalizeRestartState(snapshot['systemState']);
};

const extractResourceSnapshotValue = (snapshot: JsonValue | null | undefined): JsonValue | null => {
    if (!isObject(snapshot) || !('value' in snapshot)) {
        return null;
    }
    const value = snapshot['value'];
    return isJsonValue(value) ? value : null;
};

const fetchRestartState = async (): Promise<RestartState> => {
    const statusStreamId = getStatusStreamId();
    const resources = getStreamResources();
    await ensureStreamManagerReady(resources, { allowDiscovery: true });
    const state = resources.getResource(statusStreamId, { state: true });
    const value = extractResourceSnapshotValue(isJsonValue(state) ? state : null);
    if (value !== null) {
        return extractCanonicalState(value);
    }
    await resources.ensureResourceStarted(statusStreamId);
    const updatedState = resources.getResource(statusStreamId, { state: true });
    const updatedValue = extractResourceSnapshotValue(isJsonValue(updatedState) ? updatedState : null);
    if (updatedValue !== null) {
        return extractCanonicalState(updatedValue);
    }
    return createEmptyRestartState();
};

export { fetchRestartState, normalizeRestartState, normalizeReasons, normalizeNotifications, extractCanonicalState, createEmptyRestartState };

export type { RestartState, RestartNotification };
