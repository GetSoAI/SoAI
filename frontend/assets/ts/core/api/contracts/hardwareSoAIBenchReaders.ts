/* SoAI - Shared frontend API contract boundary hardware SoAI bench readers [frontend/assets/ts/core/api/contracts/hardwareSoAIBenchReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn, isBoolean, isFiniteNumber, isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const readSoAIBenchOptionalNumber = (record: JsonObject, key: string, label: string): number | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null || isFiniteNumber(value)) return value;
    throw new TypeError(`${label}.${key} must be a finite number or null`);
};

const readSoAIBenchOptionalString = (record: JsonObject, key: string, label: string): string | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null || isString(value)) return value;
    throw new TypeError(`${label}.${key} must be a string or null`);
};

const readSoAIBenchOptionalBoolean = (record: JsonObject, key: string, label: string): boolean | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null || isBoolean(value)) return value;
    throw new TypeError(`${label}.${key} must be a boolean or null`);
};

const readSoAIBenchOptionalStringList = (record: JsonObject, key: string, label: string): string[] | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null) return null;
    if (!Array.isArray(value) || !value.every(isString)) throw new TypeError(`${label}.${key} must be a string array or null`);
    return value;
};

export { readSoAIBenchOptionalBoolean, readSoAIBenchOptionalNumber, readSoAIBenchOptionalString, readSoAIBenchOptionalStringList };
