/* SoAI - Deeply immutable resource value publication [frontend/assets/ts/core/realtime/streammanager/resources/resourceValue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneJsonValue } from '@core/primitives/clone.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const freezeJsonValue = (value: JsonValue): JsonValue => {
    if (Array.isArray(value)) return Object.freeze(value.map((entry) => freezeJsonValue(entry)));
    if (!isJsonObject(value)) return value;
    const frozenRecord: JsonObject = {};
    for (const [key, entry] of Object.entries(value)) frozenRecord[key] = freezeJsonValue(entry);
    return Object.freeze(frozenRecord);
};

const createImmutableResourceValue = (value: JsonValue): JsonValue => freezeJsonValue(cloneJsonValue(value));

export { createImmutableResourceValue, freezeJsonValue };
