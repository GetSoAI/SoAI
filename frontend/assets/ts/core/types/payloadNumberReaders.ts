/* SoAI - Shared types payload number readers [frontend/assets/ts/core/types/payloadNumberReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isFiniteNumberValue = <T>(value: T): value is T & number => typeof value === 'number' && Number.isFinite(value);

const isFiniteIntegerValue = <T>(value: T): value is T & number => isFiniteNumberValue(value) && Number.isInteger(value);

const readRequiredFiniteNumberValue = <T>(value: T, label: string): number => {
    if (!isFiniteNumberValue(value)) {
        throw new Error(`${label} must be a finite number.`);
    }
    return value;
};

const readNullableFiniteNumberValue = <T>(value: T, label: string): number | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return readRequiredFiniteNumberValue(value, label);
};

const readFiniteNumberOrNullValue = <T>(value: T): number | null => {
    return isFiniteNumberValue(value) ? value : null;
};

const readNullableFiniteIntegerValue = <T>(value: T, label: string): number | null => {
    if (value === null || value === undefined) {
        return null;
    }
    if (!isFiniteIntegerValue(value)) {
        throw new Error(`${label} must be an integer.`);
    }
    return value;
};

const readFiniteIntegerOrNullValue = <T>(value: T): number | null => {
    return isFiniteIntegerValue(value) ? value : null;
};

const readRequiredFiniteIntegerValue = <T>(value: T, label: string): number => {
    if (!isFiniteIntegerValue(value)) {
        throw new Error(`${label} must be an integer.`);
    }
    return value;
};

const readRequiredPositiveIntegerValue = <T>(value: T, label: string): number => {
    const integer = readRequiredFiniteIntegerValue(value, label);
    if (integer <= 0) {
        throw new Error(`${label} must be a positive integer.`);
    }
    return integer;
};

const readRequiredPositiveSafeIntegerValue = <T>(value: T, label: string): number => {
    const integer = readRequiredPositiveIntegerValue(value, label);
    if (!Number.isSafeInteger(integer)) {
        throw new Error(`${label} must be a positive JavaScript-safe integer.`);
    }
    return integer;
};

const readRequiredNonNegativeIntegerValue = <T>(value: T, label: string): number => {
    const integer = readRequiredFiniteIntegerValue(value, label);
    if (integer < 0) {
        throw new Error(`${label} must be a non-negative integer.`);
    }
    return integer;
};

const readNullableNonNegativeIntegerValue = <T>(value: T, label: string): number | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return readRequiredNonNegativeIntegerValue(value, label);
};

const readNonNegativeIntegerOrNullValue = <T>(value: T): number | null => {
    const integer = readFiniteIntegerOrNullValue(value);
    return integer !== null && integer >= 0 ? integer : null;
};

const readPositiveIntegerOrNullValue = <T>(value: T): number | null => {
    const integer = readFiniteIntegerOrNullValue(value);
    return integer !== null && integer > 0 ? integer : null;
};

const readNonNegativeFiniteNumberOrNullValue = <T>(value: T): number | null => {
    const numberValue = readFiniteNumberOrNullValue(value);
    return numberValue !== null && numberValue >= 0 ? numberValue : null;
};

const readPositiveFlooredIntegerOrNullValue = <T>(value: T): number | null => {
    const numberValue = readFiniteNumberOrNullValue(value);
    if (numberValue === null) {
        return null;
    }
    const integer = Math.floor(numberValue);
    return integer > 0 ? integer : null;
};

const readRequiredPositiveTruncatedIntegerValue = <T>(value: T, label: string): number => {
    const numberValue = readRequiredFiniteNumberValue(value, label);
    const integer = Math.trunc(numberValue);
    if (integer <= 0) {
        throw new TypeError(`${label} must be > 0`);
    }
    return integer;
};

const readRequiredNonNegativeTruncatedIntegerValue = <T>(value: T, label: string): number => {
    const numberValue = readRequiredFiniteNumberValue(value, label);
    const integer = Math.trunc(numberValue);
    if (integer < 0) {
        throw new TypeError(`${label} must be >= 0`);
    }
    return integer;
};

const readBoundedPositiveIntegerTextOrNullValue = (value: string, maximum: number): number | null => {
    const raw = value.trim();
    if (!raw) {
        return null;
    }
    if (!/^\d+$/.test(raw)) {
        return null;
    }
    const numericValue = Number(raw);
    return Number.isInteger(numericValue) && numericValue > 0 && numericValue <= maximum ? numericValue : null;
};

const readRequiredPositiveIntegerTextValue = (value: string, errorMessage: string): number => {
    const numericValue = Number(value.trim());
    if (!Number.isInteger(numericValue) || numericValue <= 0) {
        throw new Error(errorMessage);
    }
    return numericValue;
};

export { readBoundedPositiveIntegerTextOrNullValue, readFiniteIntegerOrNullValue, readFiniteNumberOrNullValue, readNonNegativeFiniteNumberOrNullValue, readNonNegativeIntegerOrNullValue, readNullableFiniteIntegerValue, readNullableFiniteNumberValue, readNullableNonNegativeIntegerValue, readPositiveFlooredIntegerOrNullValue, readPositiveIntegerOrNullValue, readRequiredFiniteIntegerValue, readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue, readRequiredNonNegativeTruncatedIntegerValue, readRequiredPositiveIntegerTextValue, readRequiredPositiveIntegerValue, readRequiredPositiveSafeIntegerValue, readRequiredPositiveTruncatedIntegerValue };
