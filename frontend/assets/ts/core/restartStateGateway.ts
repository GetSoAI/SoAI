/* SoAI - Shared frontend restart state gateway [frontend/assets/ts/core/restartStateGateway.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getStreamResources } from '@core/realtime/streammanager/public.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import { STATUS } from '@core/realtime/streammanager/resources/ids.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { resolveHttpUrl } from '@core/security/public.ts';
import { readRequiredPositiveSafeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredEnumValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isBoolean, isFiniteNumber, isObject, isString, hasOwn } from '@core/typeGuards.ts';

interface RestartNotification {
    reason: string;
    path: string | null;
    timestamp: number | null;
}

type ConnectionScheme = 'http' | 'https';
type ConnectionTransitionDestination = 'same_address' | 'public_origin' | 'manual';

interface ConnectionTransition {
    configurationRevision: number;
    instanceId: string;
    currentScheme: ConnectionScheme;
    requestedScheme: ConnectionScheme;
    destination: ConnectionTransitionDestination;
    publicOrigin: string | null;
}

interface RestartState {
    required: boolean;
    timestamp: number | null;
    pid: number | null;
    reasons: string[];
    notifications: RestartNotification[];
    connectionTransition: ConnectionTransition | null;
}

const CONNECTION_SCHEMES: readonly ConnectionScheme[] = ['http', 'https'];
const CONNECTION_TRANSITION_DESTINATIONS: readonly ConnectionTransitionDestination[] = ['same_address', 'public_origin', 'manual'];
const CONNECTION_TRANSITION_KEYS = ['configuration_revision', 'instance_id', 'current_scheme', 'requested_scheme', 'destination', 'public_origin'];

const normalizeReasons = (source: JsonValue | null | undefined): string[] => {
    if (!isArray(source)) throw new Error('Restart state reasons must be an array');
    return source.map((entry) => {
        if (!isString(entry)) throw new Error('Restart state reason must be a string');
        const trimmed = entry.trim();
        if (!trimmed) throw new Error('Restart state reason must not be empty');
        return trimmed;
    });
};

const normalizeNotifications = (source: JsonValue | null | undefined): RestartNotification[] => {
    if (!isArray(source)) throw new Error('Restart state notifications must be an array');
    return source.map((entry) => {
        if (!isObject(entry)) throw new Error('Restart state notification must be an object');
        const reason = isString(entry['reason']) ? entry['reason'].trim() : '';
        if (!reason) throw new Error('Restart state notification reason must be a non-empty string');
        const path = isString(entry['path']) && entry['path'].trim().length ? entry['path'].trim() : null;
        const timestamp = isFiniteNumber(entry['timestamp']) ? Number(entry['timestamp']) : null;
        return { reason, path, timestamp };
    });
};

const decodeConnectionTransition = (source: JsonValue): ConnectionTransition => {
    const label = 'Restart state connection_transition';
    const record = requireRecord(source, label);
    assertExactRecordKeys(record, CONNECTION_TRANSITION_KEYS, label);
    const destination = readRequiredEnumValue(record['destination'], `${label}.destination`, CONNECTION_TRANSITION_DESTINATIONS);
    const publicOrigin = readNullableTrimmedStringValue(record['public_origin'], `${label}.public_origin`);
    if ((destination === 'public_origin') !== (publicOrigin !== null)) throw new Error(`${label}.public_origin must be present only for public-origin destinations.`);
    if (publicOrigin !== null) {
        const resolved = resolveHttpUrl(publicOrigin);
        if (resolved === null) throw new Error(`${label}.public_origin must be an HTTP origin.`);
        const origin = new URL(resolved);
        if (origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash) throw new Error(`${label}.public_origin must contain only an origin.`);
    }
    return {
        configurationRevision: readRequiredPositiveSafeIntegerValue(record['configuration_revision'], `${label}.configuration_revision`),
        instanceId: readRequiredTrimmedStringValue(record['instance_id'], `${label}.instance_id`),
        currentScheme: readRequiredEnumValue(record['current_scheme'], `${label}.current_scheme`, CONNECTION_SCHEMES),
        requestedScheme: readRequiredEnumValue(record['requested_scheme'], `${label}.requested_scheme`, CONNECTION_SCHEMES),
        destination,
        publicOrigin
    };
};

const normalizeConnectionTransition = (source: JsonValue | undefined): ConnectionTransition | null => {
    if (source === undefined || source === null) return null;
    try {
        return decodeConnectionTransition(source);
    } catch (error) {
        errorHandler.warn('RestartStateGateway', 'Ignoring malformed restart connection transition', ensureError(error));
        return null;
    }
};

const normalizeRestartState = (payload: JsonValue | null | undefined): RestartState => {
    if (!isObject(payload)) throw new Error('Restart state payload must be an object');
    if (!isBoolean(payload['required'])) throw new Error('Restart state payload missing required flag');
    return {
        required: payload['required'],
        timestamp: isFiniteNumber(payload['timestamp']) ? Number(payload['timestamp']) : null,
        pid: isFiniteNumber(payload['pid']) ? Number(payload['pid']) : null,
        reasons: normalizeReasons(payload['reasons']),
        notifications: normalizeNotifications(payload['notifications']),
        connectionTransition: normalizeConnectionTransition(payload['connection_transition'])
    };
};

const createEmptyRestartState = (): RestartState => ({ required: false, timestamp: null, pid: null, reasons: [], notifications: [], connectionTransition: null });

const extractCanonicalState = (snapshot: JsonValue | null | undefined): RestartState => {
    if (!isObject(snapshot)) throw new Error('Restart state snapshot must be an object');
    if (!hasOwn(snapshot, 'systemState')) throw new Error('Restart state snapshot missing systemState key');
    return normalizeRestartState(snapshot['systemState']);
};

const extractResourceSnapshotValue = (snapshot: JsonValue | null | undefined): JsonValue | null => {
    if (!isObject(snapshot) || !('value' in snapshot)) return null;
    const value = snapshot['value'];
    return isJsonValue(value) ? value : null;
};

const fetchRestartState = async (): Promise<RestartState> => {
    const resources = getStreamResources();
    await ensureStreamManagerReady(resources, { allowDiscovery: true });
    const state = resources.getResource(STATUS, { state: true });
    const value = extractResourceSnapshotValue(isJsonValue(state) ? state : null);
    if (value !== null) return extractCanonicalState(value);
    await resources.ensureResourceStarted(STATUS);
    const updatedState = resources.getResource(STATUS, { state: true });
    const updatedValue = extractResourceSnapshotValue(isJsonValue(updatedState) ? updatedState : null);
    return updatedValue === null ? createEmptyRestartState() : extractCanonicalState(updatedValue);
};

export { fetchRestartState, normalizeRestartState, normalizeReasons, normalizeNotifications, extractCanonicalState, createEmptyRestartState };
export type { ConnectionScheme, ConnectionTransition, RestartState, RestartNotification };
