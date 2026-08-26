/* SoAI - Persisted connection endpoint V1 contract [frontend/assets/ts/core/connectionstate/connectionEndpoint.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isObject, isString } from '@core/typeGuards.ts';

interface ConnectionEndpoint {
    readonly baseUrl: string;
    readonly instanceId: string;
}

const schemaVersionKey = 'schema_version';
const baseUrlKey = 'base_url';
const instanceIdKey = 'instance_id';
const CONNECTION_ENDPOINT_KEYS = new Set([schemaVersionKey, baseUrlKey, instanceIdKey]);

const encodeConnectionEndpoint = (endpoint: ConnectionEndpoint): JsonObject => ({
    [schemaVersionKey]: 1,
    [baseUrlKey]: endpoint.baseUrl,
    [instanceIdKey]: endpoint.instanceId
});

const decodeConnectionEndpoint = (value: JsonValue): ConnectionEndpoint | null => {
    if (!isObject(value)) {
        return null;
    }
    const keys = Object.keys(value);
    if (keys.length !== CONNECTION_ENDPOINT_KEYS.size || keys.some((key) => !CONNECTION_ENDPOINT_KEYS.has(key))) {
        return null;
    }
    if (value[schemaVersionKey] !== 1) {
        return null;
    }
    const baseUrl = value[baseUrlKey];
    const instanceId = value[instanceIdKey];
    if (!isString(baseUrl) || !baseUrl.trim()) {
        return null;
    }
    if (!isString(instanceId) || !instanceId.trim()) {
        return null;
    }
    return {
        baseUrl: baseUrl.trim(),
        instanceId: instanceId.trim()
    };
};

export { decodeConnectionEndpoint, encodeConnectionEndpoint };
export type { ConnectionEndpoint };
