/* SoAI - Shared types payload field readers [frontend/assets/ts/core/types/payloadFieldReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { readRequiredJsonObjectArrayValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableTrimmedStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';

type IndexedPayloadRecord<TValue> = {
    [key: string]: TValue | undefined;
};

const hasOwnField = <TValue>(record: IndexedPayloadRecord<TValue>, key: string): boolean => Object.prototype.hasOwnProperty.call(record, key);

const readRequiredRecordArrayField = <TValue>(record: IndexedPayloadRecord<TValue>, key: string, label: string): JsonObject[] => {
    if (!hasOwnField(record, key)) {
        throw new Error(`${label} is required.`);
    }
    return readRequiredJsonObjectArrayValue(record[key], label);
};

const readOptionalRecordArrayField = <TValue>(record: IndexedPayloadRecord<TValue>, key: string, label: string): JsonObject[] => {
    if (!hasOwnField(record, key) || record[key] === null || record[key] === undefined) {
        return [];
    }
    return readRequiredJsonObjectArrayValue(record[key], label);
};

const readRequiredTrimmedStringField = <TValue>(record: IndexedPayloadRecord<TValue>, key: string, label: string): string => {
    if (!hasOwnField(record, key)) {
        throw new Error(`${label} is required.`);
    }
    return readRequiredTrimmedStringValue(record[key], label);
};

const readRequiredFiniteNumberField = <TValue>(record: IndexedPayloadRecord<TValue>, key: string, label: string): number => {
    if (!hasOwnField(record, key)) {
        throw new Error(`${label} is required.`);
    }
    return readRequiredFiniteNumberValue(record[key], label);
};

const readRequiredNullableTrimmedStringField = <TValue>(record: IndexedPayloadRecord<TValue>, key: string, label: string): string | null => {
    if (!hasOwnField(record, key)) {
        throw new Error(`${label} is required.`);
    }
    return readNullableTrimmedStringValue(record[key], label);
};

const readCreatedIdField = <T>(value: T, key: string, label: string): string => {
    const record = requireRecord(value, label);
    return readRequiredTrimmedStringField(record, key, `${label}.${key}`);
};

export { readCreatedIdField, readOptionalRecordArrayField, readRequiredFiniteNumberField, readRequiredNullableTrimmedStringField, readRequiredRecordArrayField, readRequiredTrimmedStringField };
