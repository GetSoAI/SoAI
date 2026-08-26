/* SoAI - Shared types payload value readers [frontend/assets/ts/core/types/payloadValueReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { EPOCH_MS_MIN, isEpochMsNumber } from '@core/time/epochMs.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';

type IndexedPayloadRecord<TValue> = {
    [key: string]: TValue | undefined;
};

const hasOwnField = <TValue>(record: IndexedPayloadRecord<TValue>, key: string): boolean => Object.prototype.hasOwnProperty.call(record, key);

const readRequiredTrimmedString = <TValue>(record: IndexedPayloadRecord<TValue>, key: string, label: string): string => {
    if (!hasOwnField(record, key)) {
        throw new Error(`${label} is required.`);
    }
    return readRequiredTrimmedStringValue(record[key], label);
};

const readOptionalTrimmedString = <TValue>(record: IndexedPayloadRecord<TValue>, key: string): string | null => {
    if (!hasOwnField(record, key)) {
        return null;
    }
    const raw = record[key];
    if (typeof raw !== 'string') {
        return null;
    }
    const normalized = raw.trim();
    return normalized ? normalized : null;
};

const readRequiredRecordValue = <T>(value: T, label: string): JsonObject => {
    if (!isJsonObject(value)) {
        throw new Error(`${label} must be an object.`);
    }
    return value;
};

const readOptionalRecordValue = <T>(value: T, label: string): JsonObject | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return readRequiredRecordValue(value, label);
};

const optionalTrimmedString = <T>(value: T): string | null => {
    if (typeof value !== 'string') {
        return null;
    }
    const normalized = value.trim();
    return normalized ? normalized : null;
};

const readBooleanOrTrueStringValue = <T>(value: T): boolean | null => {
    if (typeof value === 'boolean') {
        return value;
    }
    if (typeof value === 'string') {
        return value === 'true';
    }
    return null;
};

const readNullableTrimmedStringValue = <T>(value: T, label: string): string | null => {
    if (value === null || value === undefined) {
        return null;
    }
    if (typeof value !== 'string') {
        throw new Error(`${label} must be a string.`);
    }
    const normalized = value.trim();
    return normalized ? normalized : null;
};

const readRequiredStringValue = <T>(value: T, label: string): string => {
    if (typeof value !== 'string') {
        throw new Error(`${label} must be a string.`);
    }
    return value;
};

const readRequiredNonEmptyStringValue = <T>(value: T, label: string): string => {
    const stringValue = readRequiredStringValue(value, label);
    if (!stringValue.trim()) {
        throw new Error(`${label} must be a non-empty string.`);
    }
    return stringValue;
};

const readRequiredTrimmedStringValue = <T>(value: T, label: string): string => {
    const normalized = readNullableTrimmedStringValue(value, label);
    if (normalized === null) {
        throw new Error(`${label} must be a non-empty string.`);
    }
    return normalized;
};

const readRequiredTrimmedStringMessageValue = <T>(value: T, errorMessage: string): string => {
    const normalized = optionalTrimmedString(value);
    if (normalized === null) {
        throw new Error(errorMessage);
    }
    return normalized;
};

const readOptionalPayloadStringValue = <T>(value: T): string | null => {
    if (value === null || value === undefined) {
        return null;
    }
    if (typeof value !== 'string') {
        return null;
    }
    const normalized = value.trim();
    return normalized || null;
};

const readRequiredPayloadStringValue = <T>(value: T, label: string): string => {
    const normalized = readOptionalPayloadStringValue(value);
    if (normalized === null) {
        throw new Error(`${label} must be a non-empty string.`);
    }
    return normalized;
};

const readRequiredBooleanValue = <T>(value: T, label: string): boolean => {
    if (typeof value !== 'boolean') {
        throw new Error(`${label} must be a boolean.`);
    }
    return value;
};

const readNullableBooleanValue = <T>(value: T, label: string): boolean | null => {
    if (value === null || value === undefined) {
        return null;
    }
    if (typeof value !== 'boolean') {
        throw new Error(`${label} must be a boolean.`);
    }
    return value;
};

const readOptionalStringValue = <T>(value: T, label: string): string | undefined => {
    if (value === null || value === undefined) {
        return undefined;
    }
    if (typeof value !== 'string') {
        throw new TypeError(`${label} must be a string when provided`);
    }
    return value;
};

const readOptionalFiniteNumberValue = <T>(value: T, label: string): number | undefined => {
    if (value === null || value === undefined) {
        return undefined;
    }
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        throw new TypeError(`${label} must be a finite number when provided`);
    }
    return value;
};

const readOptionalBooleanValue = <T>(value: T, label: string): boolean | undefined => {
    if (value === null || value === undefined) {
        return undefined;
    }
    if (typeof value !== 'boolean') {
        throw new TypeError(`${label} must be a boolean when provided`);
    }
    return value;
};

const readRequiredEpochMsValue = <T>(value: T, label: string): number => {
    if (typeof value !== 'number' || !isEpochMsNumber(value)) {
        throw new Error(`${label} must be an epoch millisecond timestamp >= ${String(EPOCH_MS_MIN)}.`);
    }
    return value;
};

const readNullableEpochMsValue = <T>(value: T, label: string): number | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return readRequiredEpochMsValue(value, label);
};

const readRequiredEnumValue = <T, TValue extends string>(value: T, label: string, values: readonly TValue[]): TValue => {
    if (typeof value !== 'string') {
        throw new Error(`${label} must be a string.`);
    }
    const normalized = value.trim();
    const enumValue = readAllowedStringValue(normalized, values);
    if (enumValue !== null) {
        return enumValue;
    }
    throw new Error(`${label} is invalid.`);
};

const readAllowedStringValue = <T, TValue extends string>(value: T, values: readonly TValue[]): TValue | null => {
    if (typeof value !== 'string') {
        return null;
    }
    const normalizedValue: string = value;
    for (const allowed of values) {
        if (normalizedValue === allowed) {
            return allowed;
        }
    }
    return null;
};

const isAllowedStringValue = <T, TValue extends string>(value: T, values: readonly TValue[]): value is T & TValue => readAllowedStringValue(value, values) !== null;

const readString = <TValue>(record: IndexedPayloadRecord<TValue>, key: string): string | null => {
    const value = record[key];
    return typeof value === 'string' ? value : null;
};

const readNumber = <TValue>(record: IndexedPayloadRecord<TValue>, key: string): number | null => {
    const value = record[key];
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
};

const readBoolean = <TValue>(record: IndexedPayloadRecord<TValue>, key: string): boolean | null => {
    const value = record[key];
    return typeof value === 'boolean' ? value : null;
};

const readInteger = <TValue>(record: IndexedPayloadRecord<TValue>, key: string): number | null => {
    const value = record[key];
    return typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value) ? value : null;
};

export { isAllowedStringValue, optionalTrimmedString, readAllowedStringValue, readBoolean, readBooleanOrTrueStringValue, readInteger, readNullableBooleanValue, readNullableEpochMsValue, readNullableTrimmedStringValue, readNumber, readOptionalBooleanValue, readOptionalFiniteNumberValue, readOptionalPayloadStringValue, readOptionalRecordValue, readOptionalStringValue, readOptionalTrimmedString, readRequiredBooleanValue, readRequiredEnumValue, readRequiredEpochMsValue, readRequiredNonEmptyStringValue, readRequiredPayloadStringValue, readRequiredRecordValue, readRequiredStringValue, readRequiredTrimmedString, readRequiredTrimmedStringMessageValue, readRequiredTrimmedStringValue, readString };
