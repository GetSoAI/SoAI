/* SoAI - Deeply immutable resource value publication [frontend/assets/ts/core/realtime/streammanager/resources/resourceValue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneJsonValue } from '@core/primitives/clone.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type ResourceRecordGuard = (value: JsonValue) => value is JsonObject;

const freezeResourceValue = (value: JsonValue, isRecord: ResourceRecordGuard): JsonValue => {
    if (isArray(value)) return Object.freeze(value.map((entry) => freezeResourceValue(entry, isRecord)));
    if (value === null || typeof value !== 'object') return value;
    if (!isRecord(value)) return value;
    const frozenRecord: JsonObject = {};
    for (const [key, entry] of Object.entries(value)) frozenRecord[key] = freezeResourceValue(entry, isRecord);
    return Object.freeze(frozenRecord);
};

const freezeJsonValue = (value: JsonValue): JsonValue => freezeResourceValue(value, isJsonObject);

const createImmutableResourceValue = (value: JsonValue): JsonValue => freezeResourceValue(cloneJsonValue(value), isObject);

export { createImmutableResourceValue, freezeJsonValue };
