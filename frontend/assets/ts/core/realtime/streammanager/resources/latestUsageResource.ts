/* SoAI - Strict revisioned latest-usage realtime resources [frontend/assets/ts/core/realtime/streammanager/resources/latestUsageResource.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { unwrap } from '@core/realtime/streammanager/resources/normalizers.ts';
import type { ResourceContext, ResourceFactory } from '@core/realtime/streammanager/types.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type LatestUsageResource = JsonObject & {
    identity: string | null;
    lastUsedAtMs: number | null;
    revision: number;
};

const decodeLatestUsageResource = (payload: JsonValue | null, identityField: string): LatestUsageResource => {
    if (!isJsonObject(payload)) throw new TypeError('Latest usage resource must be an object');
    const expectedKeys = new Set([identityField, 'last_used_at_ms', 'revision']);
    const keys = Object.keys(payload);
    if (keys.length !== expectedKeys.size || keys.some((key) => !expectedKeys.has(key))) throw new TypeError('Latest usage resource contains invalid fields');
    const revision = readRequiredNonNegativeIntegerValue(payload['revision'], 'Latest usage revision');
    const identityValue = payload[identityField];
    const timestampValue = payload['last_used_at_ms'];
    if (revision === 0) {
        if (identityValue !== null || timestampValue !== null) throw new TypeError('Empty latest usage resource must contain null identity and timestamp');
        return { identity: null, lastUsedAtMs: null, revision };
    }
    const identity = toTrimmedString(identityValue);
    const lastUsedAtMs = readRequiredNonNegativeIntegerValue(timestampValue, 'Latest usage timestamp');
    if (!identity || lastUsedAtMs <= 0) throw new TypeError('Non-empty latest usage resource requires identity and timestamp');
    return { identity, lastUsedAtMs, revision };
};

const assertLatestUsageResourceValue: (value: JsonObject) => asserts value is LatestUsageResource = (value) => {
    const expectedKeys = new Set(['identity', 'lastUsedAtMs', 'revision']);
    const keys = Object.keys(value);
    if (keys.length !== expectedKeys.size || keys.some((key) => !expectedKeys.has(key))) throw new TypeError('Latest usage resource value contains invalid fields');
    const identityValue = value['identity'];
    const timestampValue = value['lastUsedAtMs'];
    if (identityValue !== null && typeof identityValue !== 'string') throw new TypeError('Latest usage resource identity is invalid');
    const revision = readRequiredNonNegativeIntegerValue(value['revision'], 'Latest usage revision');
    const lastUsedAtMs = timestampValue === null ? null : readRequiredNonNegativeIntegerValue(timestampValue, 'Latest usage timestamp');
    if (revision === 0 && (identityValue !== null || lastUsedAtMs !== null)) throw new TypeError('Empty latest usage resource value is invalid');
    if (revision > 0 && (!identityValue || identityValue !== identityValue.trim() || lastUsedAtMs === null || lastUsedAtMs <= 0)) throw new TypeError('Non-empty latest usage resource value is invalid');
};

const readPreviousLatestUsage = (value: JsonValue | null): LatestUsageResource | null => {
    if (!isJsonObject(value)) return null;
    assertLatestUsageResourceValue(value);
    return value;
};

const requireLatestUsageResourceValue = (value: JsonValue | null): LatestUsageResource => {
    const resource = readPreviousLatestUsage(value);
    if (resource === null) throw new TypeError('Latest usage resource value is invalid');
    return resource;
};

const createLatestUsageResource =
    (identityField: string): ResourceFactory<LatestUsageResource> =>
    () => ({
        websocketOnly: true,
        skipUnchangedTransform: true,
        normalize: (payload) => unwrap(payload),
        transform: (payload, context?: ResourceContext): LatestUsageResource => {
            const next = decodeLatestUsageResource(payload, identityField);
            const previous = readPreviousLatestUsage(context?.previousValue ?? null);
            if (context?.type !== 'websocket-push' || previous === null) return next;
            if (next.revision > previous.revision) return next;
            if (next.revision < previous.revision) return previous;
            if (next.identity !== previous.identity || next.lastUsedAtMs !== previous.lastUsedAtMs) throw new TypeError('Latest usage resource conflicts at an equal revision');
            return previous;
        }
    });

export { createLatestUsageResource, decodeLatestUsageResource, requireLatestUsageResourceValue };
export type { LatestUsageResource };
