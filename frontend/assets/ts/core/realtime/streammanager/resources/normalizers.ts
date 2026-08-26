/* SoAI - Shared realtime normalizers [frontend/assets/ts/core/realtime/streammanager/resources/normalizers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { OPENAI_CAPABILITY_OVERRIDE_CATEGORIES } from '@core/openai/capabilityCategories.ts';
import type { ResourceFactory } from '@core/realtime/streammanager/types.ts';
import { hasOwn, isArray, isObject, isString } from '@core/typeGuards.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const unwrap = (payload: JsonValue | null): JsonValue | null => {
    if (isObject(payload)) {
        if (hasOwn(payload, 'payload') && hasOwn(payload, 'type')) {
            const nestedPayload = payload['payload'];
            return isJsonValue(nestedPayload) ? nestedPayload : null;
        }
    }
    return payload;
};

const normApi = (payload: JsonValue | null): JsonValue | null => unwrap(payload);

const normPrompt = (payload: JsonValue | null | undefined): JsonObject | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const resolvedId = payload['id'] ?? null;
    const resolvedName = isString(payload['name']) ? payload['name'] : '';
    const normalized = { ...Object.fromEntries(Object.entries(payload)), id: resolvedId, name: resolvedName };
    return normalized.id ? normalized : null;
};

const normCaps = (payload: JsonValue | null | undefined): JsonObject => {
    if (!isJsonObject(payload)) {
        throw new TypeError('Invalid capabilities data');
    }
    const normalized: JsonObject = {};
    for (const category of OPENAI_CAPABILITY_OVERRIDE_CATEGORIES) {
        const source = isArray(payload[category]) ? payload[category] : [];
        const entries: string[] = [];
        const seen = new Set<string>();
        for (const value of source) {
            const trimmed = toTrimmedString(value).toLowerCase();
            if (!trimmed || seen.has(trimmed)) {
                continue;
            }
            seen.add(trimmed);
            entries.push(trimmed);
        }
        normalized[category] = entries;
    }
    return Object.freeze(normalized);
};

const webSocketResource =
    <ResourceValue extends JsonValue>(transform: (payload: JsonValue | null) => ResourceValue | null): ResourceFactory<ResourceValue> =>
    () => ({
        websocketOnly: true,
        normalize: (payload) => unwrap(payload),
        transform
    });

const identity = <T>(value: T): T => value;

export { identity, normApi, normCaps, normPrompt, unwrap, webSocketResource };
