/* SoAI - Hardware V1 boundary field readers [frontend/assets/ts/core/api/contracts/hardwareContractReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableTrimmedStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';

const readOptionalHardwareNumber = (record: JsonObject, key: string, label: string): number | undefined => {
    const value = record[key];
    return value === undefined || value === null ? undefined : readRequiredFiniteNumberValue(value, `${label}.${key}`);
};

const readOptionalHardwareString = (record: JsonObject, key: string, label: string): string | undefined => readNullableTrimmedStringValue(record[key], `${label}.${key}`) ?? undefined;

const decodeHardwareNumberArray = (value: JsonValue | undefined, label: string): number[] | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => readRequiredFiniteNumberValue(entry, `${label}[${String(index)}]`));
};

const decodeHardwareStringArray = (value: JsonValue | undefined, label: string): string[] | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => readRequiredTrimmedStringValue(entry, `${label}[${String(index)}]`));
};

export { decodeHardwareNumberArray, decodeHardwareStringArray, readOptionalHardwareNumber, readOptionalHardwareString };
