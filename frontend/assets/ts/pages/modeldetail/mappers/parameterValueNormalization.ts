/* SoAI - Model detail page mappers parameter value normalization [frontend/assets/ts/pages/modeldetail/mappers/parameterValueNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonArray, JsonValue } from '@core/types/jsonValues.ts';
import { deepClone } from '@core/primitives/clone.ts';
import { hasOwn, isArray, isBoolean, isNullOrUndefined, isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { Parameter, ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';

interface SanitizeOptions {
    treatDefaultAsNull?: boolean | undefined;
    preserveEmptyArrayItems?: boolean | undefined;
}

const filterEmpty = (arr: readonly JsonValue[]): JsonValue[] => arr.filter((item) => item !== '' && !isNullOrUndefined(item));

const numericStringPattern = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i;

const toComparableNumber = (value: JsonValue | null | undefined): number | null => {
    if (isNumber(value)) {
        return Number.isFinite(value) ? value : null;
    }
    if (!isString(value)) {
        return null;
    }
    const trimmed = value.trim();
    if (trimmed.length === 0) {
        return null;
    }
    if (!numericStringPattern.test(trimmed)) {
        return null;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
};

const areValuesEqual = (firstValue: JsonValue | null | undefined, secondValue: JsonValue | null | undefined): boolean => {
    if (firstValue === secondValue) return true;
    if (isNullOrUndefined(firstValue) && isNullOrUndefined(secondValue)) return true;
    if (isBoolean(firstValue) || isBoolean(secondValue)) {
        return (firstValue === true || firstValue === 'true') === (secondValue === true || secondValue === 'true');
    }
    if (isArray(firstValue)) {
        if (isArray(secondValue)) {
            const normalizedA = filterEmpty(firstValue);
            const normalizedB = filterEmpty(secondValue);
            return normalizedA.length === normalizedB.length && normalizedA.every((value, index) => areValuesEqual(value, normalizedB[index]));
        }
        return filterEmpty(firstValue).length === 0 && isNullOrUndefined(secondValue);
    }
    if (isArray(secondValue)) {
        return filterEmpty(secondValue).length === 0 && isNullOrUndefined(firstValue);
    }
    if (!isNullOrUndefined(firstValue) && !isNullOrUndefined(secondValue) && isObject(firstValue) && isObject(secondValue)) {
        const keysA = Object.keys(firstValue);
        const keysB = Object.keys(secondValue);
        return keysA.length === keysB.length && keysA.every((key) => keysB.includes(key) && areValuesEqual(firstValue[key], secondValue[key]));
    }
    if (isNullOrUndefined(firstValue) || isNullOrUndefined(secondValue)) return false;
    const numberA = toComparableNumber(firstValue);
    const numberB = toComparableNumber(secondValue);
    if (numberA !== null && numberB !== null) {
        return numberA === numberB;
    }
    return String(firstValue) === String(secondValue);
};

const isParameterValue = (value: JsonValue | null | undefined): value is ParameterValue => {
    if (value === null) {
        return true;
    }
    if (isString(value) || isNumber(value) || isBoolean(value)) {
        return true;
    }
    if (isArray(value)) {
        return true;
    }
    return isObject(value);
};

const sanitizeParameterValue = (parameter: Parameter | null | undefined, value: JsonValue | null | undefined, options: SanitizeOptions = {}): ParameterValue | null => {
    const { treatDefaultAsNull = true } = options;
    const { preserveEmptyArrayItems = false } = options;
    if (!parameter || !isObject(parameter)) {
        return isParameterValue(value) ? value : null;
    }
    const definition = parameter.definition && isObject(parameter.definition) ? parameter.definition : {};
    const hasDefault = parameter.hasDefault ?? definition.hasDefault ?? hasOwn(definition, 'default');
    let sanitized: JsonValue | JsonArray | null | undefined = value;
    if (definition.type === 'array') {
        const arrayValue = isArray(sanitized) ? sanitized : [];
        sanitized = preserveEmptyArrayItems ? arrayValue : arrayValue.filter((item) => item !== '' && !isNullOrUndefined(item));
    } else if (definition.type === 'object') {
        sanitized = !isNullOrUndefined(sanitized) && isObject(sanitized) ? deepClone(sanitized) : null;
    }
    if (isNullOrUndefined(sanitized) || (isNumber(sanitized) && Number.isNaN(sanitized))) {
        sanitized = null;
    }
    if (treatDefaultAsNull && hasDefault && areValuesEqual(sanitized, definition.default)) {
        return null;
    }
    if (definition.type === 'array' && !isNullOrUndefined(sanitized)) {
        if (!isArray(sanitized)) {
            throw new TypeError('Array parameter sanitize produced non-array output');
        }
        return sanitized.slice();
    }
    return isParameterValue(sanitized) ? sanitized : null;
};

export { sanitizeParameterValue, areValuesEqual };
