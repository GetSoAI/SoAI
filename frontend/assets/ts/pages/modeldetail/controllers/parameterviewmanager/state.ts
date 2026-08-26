/* SoAI - Model detail page control layer parameter view manager state [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isArray, isBoolean, isNullOrUndefined, isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';

type ArrayItemUpdateResult = { next: ParameterValue[]; isModified: boolean };

const toParameterValue = (value: JsonValue): ParameterValue => {
    if (value === null || value === undefined) {
        return null;
    }
    if (isString(value) || isBoolean(value) || isNumber(value)) {
        return value;
    }
    if (isArray(value)) {
        return value.map((item) => toParameterValue(item));
    }
    if (isObject(value)) {
        return value;
    }
    return String(value);
};

const isParameterUsingDefault = (state: ParameterStateManager, parameterKey: string): boolean => {
    const parameter = state.getParameter(parameterKey);
    const hasDefault = parameter?.hasDefault ?? parameter?.definition?.hasDefault ?? (parameter?.definition ? 'default' in parameter.definition : false);
    if (!hasDefault) {
        return false;
    }
    const definitionDefault = parameter?.definition?.default;
    return isNullOrUndefined(parameter?.currentValue) || parameter?.currentValue === definitionDefault;
};

const normalizeParameterValue = (state: ParameterStateManager, parameterKey: string, rawValue: ParameterValue): ParameterValue => {
    if (rawValue === '' || isNullOrUndefined(rawValue) || (isNumber(rawValue) && Number.isNaN(rawValue))) {
        return null;
    }
    const type = state.getParameter(parameterKey)?.definition?.type;
    const choices = state.getParameter(parameterKey)?.definition?.choices;
    if (isString(rawValue) && isArray(choices)) {
        const matchingChoice = choices.find((choice) => String(choice) === rawValue);
        if (matchingChoice !== undefined) return matchingChoice;
    }
    if (type === 'integer') {
        const numericValue = readCoercedFiniteNumberOrNullValue(rawValue);
        return numericValue !== null && Number.isInteger(numericValue) ? numericValue : null;
    }
    if (type === 'float' || type === 'number') {
        return readCoercedFiniteNumberOrNullValue(rawValue);
    }
    if (type === 'boolean') {
        return rawValue === true || rawValue === 'true';
    }
    return rawValue;
};

const parseJsonParameterValue = (json: string): ParameterValue => {
    if (json === '') {
        return null;
    }
    const parsed = parseRequiredJsonText(json);
    return toParameterValue(parsed);
};

const getArrayValueWithAppend = (state: ParameterStateManager, parameterKey: string): ParameterValue[] | null => {
    if (!parameterKey) {
        return null;
    }
    const current = state.getParameter(parameterKey)?.currentValue;
    const normalizedCurrent = isArray(current) ? current.map((item) => toParameterValue(item)) : [];
    return [...normalizedCurrent, ''];
};

const getArrayValueWithRemoval = (state: ParameterStateManager, parameterKey: string, index: number): ParameterValue[] | null => {
    if (!parameterKey || Number.isNaN(index)) {
        return null;
    }
    const current = state.getParameter(parameterKey)?.currentValue;
    if (!isArray(current)) {
        return null;
    }
    return current.filter((_unusedValue, currentIndex) => currentIndex !== index).map((item) => toParameterValue(item));
};

const setArrayItemValue = (state: ParameterStateManager, parameterKey: string, index: number, value: ParameterValue): ArrayItemUpdateResult | null => {
    const parameter = state.getParameter(parameterKey);
    if (!parameter || !Number.isInteger(index)) {
        return null;
    }
    const next = isArray(parameter.currentValue) ? parameter.currentValue.map((item) => toParameterValue(item)) : [];
    const itemType = parameter.definition?.itemType;
    if (itemType === 'integer') {
        const numericValue = readCoercedFiniteNumberOrNullValue(value);
        next[index] = numericValue !== null && Number.isInteger(numericValue) ? numericValue : null;
    } else if (itemType === 'float') {
        next[index] = readCoercedFiniteNumberOrNullValue(value);
    } else if (itemType === 'boolean') {
        next[index] = value === true || value === 'true';
    } else {
        next[index] = value;
    }
    const result = state.setParameterValue(parameterKey, next);
    if (!result) {
        return null;
    }
    return { next, isModified: result.isModified };
};

export { getArrayValueWithAppend, getArrayValueWithRemoval, isParameterUsingDefault, normalizeParameterValue, parseJsonParameterValue, setArrayItemValue };
