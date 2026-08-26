/* SoAI - Chat feature value comparison [frontend/assets/ts/features/chat/conversationsettings/valueComparison.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type ComparableJsonValue = JsonValue | undefined;
type EqualityFunctionValue = (left: ComparableJsonValue, right: ComparableJsonValue) => boolean;

const arraysEqualUnordered = (leftValues: readonly JsonValue[], rightValues: readonly JsonValue[], equals: EqualityFunctionValue): boolean => {
    if (leftValues.length !== rightValues.length) {
        return false;
    }

    const isPrimitive = (value: JsonValue): value is string | number | boolean | null => value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean';

    if (leftValues.every(isPrimitive) && rightValues.every(isPrimitive)) {
        const counts = new Map<string, number>();
        const keyOf = (value: string | number | boolean | null): string => {
            if (value === null) {
                return 'null';
            }
            if (typeof value === 'number') {
                return Number.isNaN(value) ? 'number:NaN' : `number:${value}`;
            }
            return `${typeof value}:${String(value)}`;
        };

        for (const value of leftValues) {
            const key = keyOf(value);
            const current = counts.get(key);
            counts.set(key, current !== undefined ? current + 1 : 1);
        }
        for (const value of rightValues) {
            const key = keyOf(value);
            const current = counts.get(key);
            const next = current !== undefined ? current - 1 : -1;
            if (next < 0) {
                return false;
            }
            if (next === 0) {
                counts.delete(key);
            } else {
                counts.set(key, next);
            }
        }
        return counts.size === 0;
    }

    const used = new Array<boolean>(rightValues.length).fill(false);
    for (const leftItem of leftValues) {
        let matched = false;
        for (let index = 0; index < rightValues.length; index += 1) {
            if (used[index]) {
                continue;
            }
            if (equals(leftItem, rightValues[index])) {
                used[index] = true;
                matched = true;
                break;
            }
        }
        if (!matched) {
            return false;
        }
    }
    return true;
};

const isJsonObjectValue = (value: ComparableJsonValue): value is JsonObject => value !== null && value !== undefined && typeof value === 'object' && !Array.isArray(value);

const compareParameterValues = (leftValue: ComparableJsonValue, rightValue: ComparableJsonValue, options?: { precision?: number | undefined }): boolean => {
    const precision = options && typeof options.precision === 'number' ? options.precision : 2;
    const scale = 10 ** precision;
    const visited = new WeakMap<WeakKey, WeakKey>();

    const deepEqual = (left: ComparableJsonValue, right: ComparableJsonValue): boolean => {
        if (left === right) {
            return true;
        }
        if (left === null && right === undefined) {
            return true;
        }
        if (left === undefined && right === null) {
            return true;
        }
        if (left === null || left === undefined || right === null || right === undefined) {
            return false;
        }

        if (typeof left === 'number' && typeof right === 'number') {
            if (!Number.isFinite(left) || !Number.isFinite(right)) {
                return Object.is(left, right);
            }
            return Math.round(left * scale) === Math.round(right * scale);
        }
        if (typeof left !== typeof right) {
            return false;
        }
        if (typeof left === 'string' || typeof left === 'boolean') {
            return left === right;
        }
        if (Array.isArray(left) && Array.isArray(right)) {
            return arraysEqualUnordered(left, right, deepEqual);
        }
        if (isJsonObjectValue(left) && isJsonObjectValue(right)) {
            const cached = visited.get(left);
            if (cached && cached === right) {
                return true;
            }
            visited.set(left, right);

            const leftKeys = Object.keys(left);
            const rightKeys = Object.keys(right);
            if (leftKeys.length !== rightKeys.length) {
                return false;
            }
            for (const key of leftKeys) {
                if (!hasOwn(right, key)) {
                    return false;
                }
                if (!deepEqual(left[key], right[key])) {
                    return false;
                }
            }
            return true;
        }
        return false;
    };

    return deepEqual(leftValue, rightValue);
};

export { compareParameterValues };
