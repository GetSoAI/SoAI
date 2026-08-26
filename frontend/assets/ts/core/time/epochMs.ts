/* SoAI - Shared time epoch ms [frontend/assets/ts/core/time/epochMs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isNumber, isString } from '@core/typeGuards.ts';

const EPOCH_MS_MIN = 1_000_000_000_000;
const EPOCH_MS_MAX = 253_402_300_799_999;
const EPOCH_MS_DETECTION_FLOOR = 946_684_800_000;
const INTEGER_STRING_PATTERN = /^\d+$/;
const NUMERIC_STRING_PATTERN = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;

const isEpochMsNumber = (value: number): boolean => {
    return Number.isSafeInteger(value) && value >= EPOCH_MS_MIN && value <= EPOCH_MS_MAX;
};

const isEpochMsAtLeast = (value: number, minimum: number): boolean => {
    return Number.isSafeInteger(value) && value >= minimum && value <= EPOCH_MS_MAX;
};

type EpochMsInput = JsonValue | Date | null | undefined;

const isEpochMsValue = (value: EpochMsInput): value is number => {
    if (!isNumber(value)) {
        return false;
    }
    return isEpochMsNumber(value);
};

const parseEpochMsOrNull = (value: EpochMsInput, minimum: number = EPOCH_MS_MIN): number | null => {
    if (value instanceof Date) {
        const timestamp = value.getTime();
        return isEpochMsAtLeast(timestamp, minimum) ? timestamp : null;
    }
    if (isNumber(value)) {
        return isEpochMsAtLeast(value, minimum) ? value : null;
    }
    const trimmed = isString(value) ? value.trim() : '';
    if (!trimmed) {
        return null;
    }
    if (INTEGER_STRING_PATTERN.test(trimmed)) {
        const numeric = Number(trimmed);
        return isEpochMsAtLeast(numeric, minimum) ? numeric : null;
    }
    if (NUMERIC_STRING_PATTERN.test(trimmed)) {
        return null;
    }
    const parsed = new Date(trimmed).getTime();
    return isEpochMsAtLeast(parsed, minimum) ? parsed : null;
};

const coerceEpochMsOrFallback = (value: EpochMsInput, fallback: number, options: { minimum?: number; errorMessage?: string } = {}): number => {
    const minimum = options.minimum ?? EPOCH_MS_MIN;
    const errorMessage = options.errorMessage ?? `Timestamp must be an epoch millisecond value >= ${String(minimum)}`;
    const parsed = parseEpochMsOrNull(value, minimum);
    if (parsed !== null) {
        return parsed;
    }
    if (value instanceof Date) {
        const timestamp = value.getTime();
        if (!Number.isFinite(timestamp)) {
            return fallback;
        }
        throw new Error(errorMessage);
    }
    if (isNumber(value)) {
        throw new Error(errorMessage);
    }
    const trimmed = isString(value) ? value.trim() : '';
    if (!trimmed) {
        return fallback;
    }
    if (INTEGER_STRING_PATTERN.test(trimmed) || NUMERIC_STRING_PATTERN.test(trimmed)) {
        throw new Error(errorMessage);
    }
    const dateTimestamp = new Date(trimmed).getTime();
    if (Number.isNaN(dateTimestamp)) {
        return fallback;
    }
    throw new Error(errorMessage);
};

export { EPOCH_MS_DETECTION_FLOOR, EPOCH_MS_MAX, EPOCH_MS_MIN, coerceEpochMsOrFallback, isEpochMsNumber, isEpochMsValue, parseEpochMsOrNull };
