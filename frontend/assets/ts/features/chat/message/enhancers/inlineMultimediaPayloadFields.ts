/* SoAI - Chat feature inline multimedia payload fields [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaPayloadFields.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

type PayloadStringEnumValues<Value extends string> = readonly Value[];

const optionalPayloadString = (payload: JsonObject, fieldName: string): string | null => {
    const value = toTrimmedString(payload[fieldName]);
    return value ? value : null;
};

const requirePayloadString = (payload: JsonObject, fieldName: string, context: string): string => {
    const value = optionalPayloadString(payload, fieldName);
    if (value === null) {
        throw new Error(`${context} missing ${fieldName}`);
    }
    return value;
};

const requirePayloadRawString = (payload: JsonObject, fieldName: string, context: string): string => {
    const value = payload[fieldName];
    if (!isString(value)) {
        throw new Error(`${context} missing ${fieldName}`);
    }
    return value;
};

const requirePayloadStringEnum = <Value extends string>(payload: JsonObject, fieldName: string, context: string, values: PayloadStringEnumValues<Value>): Value => {
    const value = requirePayloadString(payload, fieldName, context);
    for (const allowedValue of values) {
        if (value === allowedValue) {
            return allowedValue;
        }
    }
    throw new Error(`${context} ${fieldName} is unsupported: ${value}`);
};

const requireAbsentPayloadString = (payload: JsonObject, fieldName: string, context: string): null => {
    const value = optionalPayloadString(payload, fieldName);
    if (value !== null) {
        throw new Error(`${context} field ${fieldName} is invalid for this type`);
    }
    return null;
};

export { optionalPayloadString, requireAbsentPayloadString, requirePayloadRawString, requirePayloadString, requirePayloadStringEnum };
