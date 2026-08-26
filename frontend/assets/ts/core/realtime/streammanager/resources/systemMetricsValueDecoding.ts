/* SoAI - System metrics V1 scalar and collection decoding [frontend/assets/ts/core/realtime/streammanager/resources/systemMetricsValueDecoding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type FieldNames = Readonly<Record<string, string>>;

const optionalMetricsObject = (record: JsonObject, wireName: string, label: string): JsonObject | undefined => {
    const value = record[wireName];
    if (value === undefined || value === null) return undefined;
    if (!isJsonObject(value)) throw new TypeError(`${label}.${wireName} must be an object`);
    return value;
};

const decodeFiniteNumber = (value: JsonValue, label: string): number => {
    if (typeof value !== 'number' || !Number.isFinite(value)) throw new TypeError(`${label} must be a finite number`);
    return value;
};

const decodeFiniteNumberFields = (source: JsonObject, fieldNames: FieldNames, label: string): JsonObject => {
    const decoded: JsonObject = {};
    for (const [wireName, domainName] of Object.entries(fieldNames)) {
        const value = source[wireName];
        if (value !== undefined && value !== null) decoded[domainName] = decodeFiniteNumber(value, `${label}.${wireName}`);
    }
    return decoded;
};

const decodeStringFields = (source: JsonObject, fieldNames: FieldNames, label: string): JsonObject => {
    const decoded: JsonObject = {};
    for (const [wireName, domainName] of Object.entries(fieldNames)) {
        const value = source[wireName];
        if (value === undefined || value === null) continue;
        if (typeof value !== 'string') throw new TypeError(`${label}.${wireName} must be a string`);
        decoded[domainName] = value;
    }
    return decoded;
};

const decodeBooleanFields = (source: JsonObject, fieldNames: FieldNames, label: string): JsonObject => {
    const decoded: JsonObject = {};
    for (const [wireName, domainName] of Object.entries(fieldNames)) {
        const value = source[wireName];
        if (value === undefined || value === null) continue;
        if (typeof value !== 'boolean') throw new TypeError(`${label}.${wireName} must be a boolean`);
        decoded[domainName] = value;
    }
    return decoded;
};

const decodeFiniteNumberMap = (value: JsonObject, label: string): JsonObject => {
    const decoded: JsonObject = {};
    for (const [entryName, entryValue] of Object.entries(value)) decoded[entryName] = decodeFiniteNumber(entryValue, `${label}.${entryName}`);
    return decoded;
};

const decodeNestedFiniteNumberMap = (value: JsonObject, label: string): JsonObject => {
    const decoded: JsonObject = {};
    for (const [entryName, entryValue] of Object.entries(value)) {
        if (!isJsonObject(entryValue)) throw new TypeError(`${label}.${entryName} must be an object`);
        decoded[entryName] = decodeFiniteNumberMap(entryValue, `${label}.${entryName}`);
    }
    return decoded;
};

const decodeFiniteNumberArray = (value: JsonValue, label: string): number[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => decodeFiniteNumber(entry, `${label}[${String(index)}]`));
};

const decodeStringArray = (value: JsonValue, label: string): string[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => {
        if (typeof entry !== 'string') throw new TypeError(`${label}[${String(index)}] must be a string`);
        return entry;
    });
};

const assignOptionalSection = (target: JsonObject, domainName: string, section: JsonObject | undefined): void => {
    if (section !== undefined) target[domainName] = section;
};

export { assignOptionalSection, decodeBooleanFields, decodeFiniteNumber, decodeFiniteNumberArray, decodeFiniteNumberFields, decodeFiniteNumberMap, decodeNestedFiniteNumberMap, decodeStringArray, decodeStringFields, optionalMetricsObject };
export type { FieldNames };
