/* SoAI - Shared types number coercion readers [frontend/assets/ts/core/types/numberCoercionReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { readFiniteNumberOrNullValue } from '@core/types/payloadNumberReaders.ts';

interface CoercedFiniteNumberOptions {
    stripThousandsSeparators?: boolean | undefined;
    allowLeadingNumericSegment?: boolean | undefined;
}

const readCoercedFiniteNumberOrNullValue = <T>(value: T, options: CoercedFiniteNumberOptions = {}): number | null => {
    const finiteNumber = readFiniteNumberOrNullValue(value);
    if (finiteNumber !== null) {
        return finiteNumber;
    }
    if (typeof value !== 'string') {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }
    const normalized = options.stripThousandsSeparators === true ? trimmed.replace(/,/g, '') : trimmed;
    const direct = Number(normalized);
    const directNumber = readFiniteNumberOrNullValue(direct);
    if (directNumber !== null) {
        return directNumber;
    }
    if (options.allowLeadingNumericSegment !== true) {
        return null;
    }
    const leadingNumericSegment = normalized.match(/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?/i)?.[0] ?? '';
    return readFiniteNumberOrNullValue(Number(leadingNumericSegment));
};

const readNumberCoercedFiniteNumberValue = <T>(value: T, errorMessage: string): number => {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
        throw new Error(errorMessage);
    }
    return numericValue;
};

const coerceRuntimeFiniteNumber = <T>(value: T): number | null => {
    if (value === null || value === undefined || typeof value === 'symbol') {
        return null;
    }
    if (typeof value === 'string' && !value.trim()) {
        return null;
    }
    try {
        const numericValue = typeof value === 'number' ? value : Number(value);
        return readFiniteNumberOrNullValue(numericValue);
    } catch (error) {
        throw ensureError(error);
    }
};

function readRuntimeFiniteNumberOrFallbackValue<T>(value: T, fallback: number): number;
function readRuntimeFiniteNumberOrFallbackValue<T>(value: T, fallback: null): number | null;
function readRuntimeFiniteNumberOrFallbackValue<T>(value: T, fallback: undefined): number | undefined;
function readRuntimeFiniteNumberOrFallbackValue<T>(value: T, fallback: number | null | undefined): number | null | undefined;
function readRuntimeFiniteNumberOrFallbackValue<T>(value: T, fallback: number | null | undefined): number | null | undefined {
    const numericValue = coerceRuntimeFiniteNumber(value);
    return numericValue === null ? fallback : numericValue;
}

const readRoundedIntegerAtLeastValue = <T>(value: T, label: string, minimum: number): number => {
    const numericValue = Math.round(Number(value));
    if (!Number.isFinite(numericValue) || numericValue < minimum) {
        throw new TypeError(`${label} must be a finite number >= ${minimum}`);
    }
    return numericValue;
};

const readRoundedIntegerMinimumValue = <T>(value: T, minimum: number): number => {
    const numericValue = Math.round(Number(value));
    if (Number.isFinite(numericValue)) {
        return Math.max(minimum, numericValue);
    }
    throw new TypeError('value must be a finite number');
};

const readRoundedPositiveIntegerOrNullValue = <T>(value: T): number | null => {
    const numericValue = Math.round(Number(value));
    return Number.isFinite(numericValue) && numericValue > 0 ? numericValue : null;
};

const readPositiveNumberRoundedIntegerOrNullValue = <T>(value: T): number | null => {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue) || numericValue <= 0) {
        return null;
    }
    return Math.max(1, Math.round(numericValue));
};

const readRoundedPositiveIntegerOrFallbackValue = <T>(value: T, fallback: number): number => {
    const numericValue = Math.round(Number(value));
    return Number.isFinite(numericValue) && numericValue > 0 ? numericValue : fallback;
};

const readClampedFiniteNumberOrFallbackValue = <T>(value: T, fallback: number, minimum: number | undefined, maximum: number | undefined): number => {
    const numericValue = readCoercedFiniteNumberOrNullValue(value);
    return numericValue !== null ? clampNumber(numericValue, minimum, maximum) : fallback;
};

const readClampedRoundedIntegerOrFallbackValue = <T>(value: T, fallback: number, minimum: number | undefined, maximum: number | undefined): number => {
    const numericValue = readCoercedFiniteNumberOrNullValue(value);
    return numericValue !== null ? clampNumber(Math.round(numericValue), minimum, maximum) : fallback;
};

const readClampedFlooredIntegerOrFallbackValue = <T>(value: T, fallback: number, minimum: number | undefined, maximum: number | undefined): number => {
    const numericValue = readCoercedFiniteNumberOrNullValue(value);
    return numericValue !== null ? clampNumber(Math.floor(numericValue), minimum, maximum) : fallback;
};

const readRequiredPositiveNumberRoundedIntegerValue = <T>(value: T, errorMessage: string): number => {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue) || numericValue <= 0) {
        throw new Error(errorMessage);
    }
    return Math.max(1, Math.round(numericValue));
};

export { readClampedFiniteNumberOrFallbackValue, readClampedFlooredIntegerOrFallbackValue, readClampedRoundedIntegerOrFallbackValue, readCoercedFiniteNumberOrNullValue, readNumberCoercedFiniteNumberValue, readPositiveNumberRoundedIntegerOrNullValue, readRequiredPositiveNumberRoundedIntegerValue, readRoundedIntegerAtLeastValue, readRoundedIntegerMinimumValue, readRoundedPositiveIntegerOrFallbackValue, readRoundedPositiveIntegerOrNullValue, readRuntimeFiniteNumberOrFallbackValue };
