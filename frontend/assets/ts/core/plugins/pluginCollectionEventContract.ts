/* SoAI - Plugin collection realtime event V1 boundary decoding [frontend/assets/ts/core/plugins/pluginCollectionEventContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isBoolean, isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface PluginCollectionEvent {
    type: string;
    pluginName: string | null;
    newState: string | null;
    context?: JsonValue | undefined;
    circuitBreaker: JsonObject;
}

const readOptionalString = (payload: JsonObject, key: string): string | null => {
    const value = payload[key];
    if (value === undefined || value === null) return null;
    if (!isString(value)) throw new TypeError(`Plugin collection event.${key} must be a string`);
    return toTrimmedString(value) || null;
};

const copyOptionalString = (payload: JsonObject, wireKey: string, domainKey: string, decoded: JsonObject): void => {
    const value = payload[wireKey];
    if (value === undefined) return;
    if (!isString(value)) throw new TypeError(`Plugin collection event.${wireKey} must be a string`);
    decoded[domainKey] = value;
};

const copyOptionalBoolean = (payload: JsonObject, wireKey: string, domainKey: string, decoded: JsonObject): void => {
    const value = payload[wireKey];
    if (value === undefined) return;
    if (!isBoolean(value)) throw new TypeError(`Plugin collection event.${wireKey} must be a boolean`);
    decoded[domainKey] = value;
};

const copyOptionalNumber = (payload: JsonObject, wireKey: string, domainKey: string, decoded: JsonObject): void => {
    const value = payload[wireKey];
    if (value === undefined) return;
    if (!isFiniteNumber(value)) throw new TypeError(`Plugin collection event.${wireKey} must be a finite number`);
    decoded[domainKey] = value;
};

const decodePluginCircuitBreakerEventFields = (payload: JsonObject): JsonObject => {
    const decoded: JsonObject = {};
    copyOptionalString(payload, 'state', 'state', decoded);
    copyOptionalBoolean(payload, 'is_open', 'isOpen', decoded);
    copyOptionalNumber(payload, 'failure_count', 'failureCount', decoded);
    copyOptionalNumber(payload, 'last_failure_at_ms', 'lastFailureAtMs', decoded);
    copyOptionalNumber(payload, 'recovery_timeout_sec', 'recoveryTimeoutSec', decoded);
    copyOptionalNumber(payload, 'failure_window_sec', 'failureWindowSec', decoded);
    copyOptionalNumber(payload, 'failure_threshold', 'failureThreshold', decoded);
    return decoded;
};

const decodePluginCollectionEvent = (value: JsonValue): PluginCollectionEvent => {
    if (!isJsonObject(value)) throw new TypeError('Plugin collection event must be an object');
    const type = readOptionalString(value, 'type');
    if (!type) throw new TypeError('Plugin collection event.type must be a non-empty string');
    const decoded: PluginCollectionEvent = {
        type,
        pluginName: readOptionalString(value, 'plugin_name'),
        newState: readOptionalString(value, 'new_state'),
        circuitBreaker: decodePluginCircuitBreakerEventFields(value)
    };
    if (value['context'] !== undefined) decoded.context = value['context'];
    return decoded;
};

export { decodePluginCollectionEvent };
export type { PluginCollectionEvent };
