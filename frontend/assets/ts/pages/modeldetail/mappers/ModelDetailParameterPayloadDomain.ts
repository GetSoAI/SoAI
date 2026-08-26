/* SoAI - Frontend model detail parameter payload boundary domain [frontend/assets/ts/pages/modeldetail/mappers/ModelDetailParameterPayloadDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn, isArray, isBoolean, isNumber, isString, isStringArray } from '@core/typeGuards.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ModelDetailParametersData } from '@pages/modeldetail/types.ts';
import type { Parameter, ParameterCategory, ParameterDefinition } from '@pages/modeldetail/contracts/parameterTypes.ts';

const optionalString = (record: JsonObject, key: string, label: string): string | undefined => {
    const value = record[key];
    if (value === undefined) return undefined;
    if (!isString(value)) throw new TypeError(`${label}.${key} must be a string.`);
    return value;
};

const optionalBoolean = (record: JsonObject, key: string, label: string): boolean | undefined => {
    const value = record[key];
    if (value === undefined) return undefined;
    if (!isBoolean(value)) throw new TypeError(`${label}.${key} must be a boolean.`);
    return value;
};

const optionalStringArray = (record: JsonObject, key: string, label: string): string[] | undefined => {
    const value = record[key];
    if (value === undefined) return undefined;
    if (!isStringArray(value)) throw new TypeError(`${label}.${key} must be a string array.`);
    return [...value];
};

const optionalFiniteNumber = (record: JsonObject, key: string, label: string): number | undefined => {
    const value = record[key];
    if (value === undefined) return undefined;
    if (!isNumber(value) || !Number.isFinite(value)) throw new TypeError(`${label}.${key} must be a finite number.`);
    return value;
};

const optionalScalarArray = (record: JsonObject, key: string, label: string): JsonValue[] | undefined => {
    const value = record[key];
    if (value === undefined) return undefined;
    if (!isArray(value) || value.length === 0 || value.some((entry) => entry === null || isArray(entry) || (typeof entry === 'object' && entry !== null) || (isNumber(entry) && !Number.isFinite(entry)))) throw new TypeError(`${label}.${key} must be a non-empty finite scalar array.`);
    if (value.some((entry, index) => value.slice(0, index).some((previous) => previous === entry))) throw new TypeError(`${label}.${key} must not contain duplicate values.`);
    return [...value];
};

const equalScalarArrays = (left: JsonValue[], right: JsonValue[]): boolean => left.length === right.length && left.every((value, index) => value === right[index]);

const PARAMETER_TYPES = new Set(['string', 'integer', 'float', 'boolean', 'array', 'object']);

const valueMatchesParameterType = (value: JsonValue, type: string): boolean => {
    if (type === 'string') return isString(value);
    if (type === 'integer') return isNumber(value) && Number.isFinite(value) && Number.isInteger(value);
    if (type === 'float') return isNumber(value) && Number.isFinite(value);
    if (type === 'boolean') return isBoolean(value);
    if (type === 'array') return isArray(value);
    return typeof value === 'object' && value !== null && !isArray(value);
};

const choicesContain = (choices: JsonValue[] | undefined, value: JsonValue): boolean => choices?.some((choice) => choice === value) === true;

const parseNumericString = (value: string, label: string): number => {
    const normalized = value.trim();
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(normalized)) throw new TypeError(`${label} must be a finite numeric string.`);
    const parsed = Number(normalized);
    if (!Number.isFinite(parsed)) throw new TypeError(`${label} must be a finite numeric string.`);
    return parsed;
};

const validateParameterValue = (definition: ParameterDefinition, value: JsonValue, label: string): void => {
    const type = definition.type;
    if (!type || !valueMatchesParameterType(value, type)) throw new TypeError(`${label} must have type '${type ?? 'unknown'}'.`);
    if (type === 'array') {
        if (!isArray(value)) throw new TypeError(`${label} must have type 'array'.`);
        const itemType = definition.itemType;
        if (!itemType || value.some((item) => !valueMatchesParameterType(item, itemType))) throw new TypeError(`${label} contains an item with an invalid type.`);
        if (definition.choices && value.some((item) => !choicesContain(definition.choices, item))) throw new TypeError(`${label} contains an item that is not allowed.`);
        if (definition.valueCount !== undefined && value.length !== definition.valueCount) throw new TypeError(`${label} must contain exactly ${definition.valueCount} values.`);
        return;
    }
    if (type === 'integer' || type === 'float') {
        if (!isNumber(value)) throw new TypeError(`${label} must be numeric.`);
        if (definition.minimum !== undefined && value < definition.minimum) throw new TypeError(`${label} is below its minimum.`);
        if (definition.maximum !== undefined && value > definition.maximum) throw new TypeError(`${label} exceeds its maximum.`);
    }
    if (type === 'string' && (definition.numericStringMinimum !== undefined || definition.numericStringMaximum !== undefined) && !choicesContain(definition.choices, value)) {
        if (!isString(value)) throw new TypeError(`${label} must be a string.`);
        const numericValue = parseNumericString(value, label);
        if (definition.numericStringMinimum !== undefined && numericValue < definition.numericStringMinimum) throw new TypeError(`${label} is below its numeric-string minimum.`);
        if (definition.numericStringMaximum !== undefined && numericValue > definition.numericStringMaximum) throw new TypeError(`${label} exceeds its numeric-string maximum.`);
        return;
    }
    if (definition.choices && !choicesContain(definition.choices, value)) throw new TypeError(`${label} is not an allowed value.`);
};

const decodeNumericBounds = (record: JsonObject, label: string): Pick<ParameterDefinition, 'minimum' | 'maximum'> => {
    const range = record['range'];
    let rangeMinimum: number | undefined;
    let rangeMaximum: number | undefined;
    if (range !== undefined) {
        if (!isArray(range) || range.length !== 2) throw new TypeError(`${label}.range must contain exactly two finite numbers.`);
        const minimumCandidate = range[0];
        const maximumCandidate = range[1];
        if (!isNumber(minimumCandidate) || !Number.isFinite(minimumCandidate) || !isNumber(maximumCandidate) || !Number.isFinite(maximumCandidate)) throw new TypeError(`${label}.range must contain exactly two finite numbers.`);
        rangeMinimum = minimumCandidate;
        rangeMaximum = maximumCandidate;
    }
    const directMinimum = optionalFiniteNumber(record, 'minimum', label);
    const directMaximum = optionalFiniteNumber(record, 'maximum', label);
    if (rangeMinimum !== undefined && directMinimum !== undefined && rangeMinimum !== directMinimum) throw new TypeError(`${label}.range and minimum contradict each other.`);
    if (rangeMaximum !== undefined && directMaximum !== undefined && rangeMaximum !== directMaximum) throw new TypeError(`${label}.range and maximum contradict each other.`);
    const minimum = directMinimum ?? rangeMinimum;
    const maximum = directMaximum ?? rangeMaximum;
    if (minimum !== undefined && maximum !== undefined && minimum > maximum) throw new TypeError(`${label} minimum must not exceed maximum.`);
    return { minimum, maximum };
};

const decodeParameterDefinition = (value: JsonValue | undefined, label: string): ParameterDefinition => {
    const record = requireRecord(value, label);
    const definition: ParameterDefinition = {};
    const displayName = optionalString(record, 'display_name', label);
    const category = optionalString(record, 'category', label);
    const group = optionalString(record, 'group', label);
    const description = optionalString(record, 'description', label);
    const aliases = optionalStringArray(record, 'aliases', label);
    const linkedParameterName = optionalString(record, 'linked_parameter_name', label);
    const isStandardizedAlias = optionalBoolean(record, 'is_standardized_alias', label);
    const requiresReload = optionalBoolean(record, 'requires_reload', label);
    const hasDefault = optionalBoolean(record, 'has_default', label);
    const type = optionalString(record, 'type', label);
    const itemType = optionalString(record, 'item_type', label);
    const { minimum, maximum } = decodeNumericBounds(record, label);
    const choices = optionalScalarArray(record, 'choices', label);
    const enumValues = optionalScalarArray(record, 'enum', label);
    if (choices !== undefined && enumValues !== undefined && !equalScalarArrays(choices, enumValues)) throw new TypeError(`${label}.choices and enum contradict each other.`);
    const normalizedChoices = choices ?? enumValues;
    const numericStringMinimum = optionalFiniteNumber(record, 'numeric_string_minimum', label);
    const numericStringMaximum = optionalFiniteNumber(record, 'numeric_string_maximum', label);
    const valueCount = optionalFiniteNumber(record, 'value_count', label);
    if (valueCount !== undefined && (!Number.isInteger(valueCount) || valueCount <= 0)) throw new TypeError(`${label}.value_count must be a positive integer.`);
    if (minimum !== undefined && maximum !== undefined && minimum > maximum) throw new TypeError(`${label} has an unordered numeric range.`);
    if (numericStringMinimum !== undefined && numericStringMaximum !== undefined && numericStringMinimum > numericStringMaximum) throw new TypeError(`${label} has unordered numeric-string bounds.`);
    if (displayName !== undefined) definition.displayName = displayName;
    if (category !== undefined) definition.category = category;
    if (group !== undefined) definition.group = group;
    if (description !== undefined) definition.description = description;
    if (aliases !== undefined) definition.aliases = aliases;
    if (linkedParameterName !== undefined) definition.linkedParameterName = linkedParameterName;
    if (isStandardizedAlias !== undefined) definition.isStandardizedAlias = isStandardizedAlias;
    if (requiresReload !== undefined) definition.requiresReload = requiresReload;
    const defaultValue = record['default'];
    if (hasDefault !== undefined) definition.hasDefault = hasDefault;
    if (type !== undefined) definition.type = type;
    if (itemType !== undefined) definition.itemType = itemType;
    if (minimum !== undefined) definition.minimum = minimum;
    if (maximum !== undefined) definition.maximum = maximum;
    if (numericStringMinimum !== undefined) definition.numericStringMinimum = numericStringMinimum;
    if (numericStringMaximum !== undefined) definition.numericStringMaximum = numericStringMaximum;
    if (valueCount !== undefined) definition.valueCount = valueCount;
    if (normalizedChoices !== undefined) definition.choices = normalizedChoices;
    if (!type || !PARAMETER_TYPES.has(type)) throw new TypeError(`${label}.type must be a supported V1 parameter type.`);
    if ((minimum !== undefined || maximum !== undefined) && type !== 'integer' && type !== 'float') throw new TypeError(`${label} numeric bounds require an integer or float type.`);
    if (type === 'integer' && [minimum, maximum].some((bound) => bound !== undefined && !Number.isInteger(bound))) throw new TypeError(`${label} integer bounds must be integers.`);
    if ((numericStringMinimum !== undefined || numericStringMaximum !== undefined) && type !== 'string') throw new TypeError(`${label} numeric-string bounds require a string type.`);
    if (type === 'array') {
        if (!itemType || !PARAMETER_TYPES.has(itemType)) throw new TypeError(`${label}.item_type must be a supported V1 parameter type.`);
        if (normalizedChoices?.some((choice) => !valueMatchesParameterType(choice, itemType))) throw new TypeError(`${label} enum items must match item_type.`);
    } else {
        if (itemType !== undefined || valueCount !== undefined) throw new TypeError(`${label} array metadata requires an array type.`);
        if (normalizedChoices?.some((choice) => !valueMatchesParameterType(choice, type))) throw new TypeError(`${label} enum items must match type.`);
    }
    if (hasDefault === undefined || hasDefault !== hasOwn(record, 'default')) throw new TypeError(`${label}.has_default contradicts default presence.`);
    if (hasDefault) {
        if (defaultValue === undefined) throw new TypeError(`${label}.default is required.`);
        validateParameterValue(definition, defaultValue, `${label}.default`);
        definition.default = defaultValue;
    }
    return definition;
};

const decodeParameter = (value: JsonValue, label: string): Parameter => {
    const record = requireRecord(value, label);
    const definition = decodeParameterDefinition(record['definition'], `${label}.definition`);
    const parameter: Parameter = { definition };
    const currentValue = record['current_value'];
    if (hasOwn(record, 'current_value') && currentValue !== undefined) {
        if (currentValue !== null) validateParameterValue(definition, currentValue, `${label}.current_value`);
        parameter.currentValue = currentValue;
    }
    const isCustom = optionalBoolean(record, 'is_custom', label);
    const hasDefault = optionalBoolean(record, 'has_default', label);
    if (isCustom !== undefined) parameter.isCustom = isCustom;
    if (hasDefault !== undefined) {
        if (hasDefault !== definition.hasDefault) throw new TypeError(`${label}.has_default contradicts definition.has_default.`);
        parameter.hasDefault = hasDefault;
    }
    return parameter;
};

const decodeCategory = (value: JsonValue, label: string): ParameterCategory => {
    if (isString(value)) return value;
    const record = requireRecord(value, label);
    const category: Exclude<ParameterCategory, string> = {};
    const title = optionalString(record, 'title', label);
    const description = optionalString(record, 'description', label);
    if (title !== undefined) category.title = title;
    if (description !== undefined) category.description = description;
    return category;
};

const decodeModelDetailParameterPayload = (value: JsonValue): ModelDetailParametersData => {
    const record = requireRecord(value, 'Model parameters payload');
    const rawParameters = requireRecord(record['parameters'], 'Model parameters payload.parameters');
    const rawCategories = requireRecord(record['categories'], 'Model parameters payload.categories');
    const parameters: NonNullable<ModelDetailParametersData['parameters']> = {};
    const categories: NonNullable<ModelDetailParametersData['categories']> = {};
    for (const [parameterName, parameterValue] of Object.entries(rawParameters)) {
        parameters[parameterName] = decodeParameter(parameterValue, `Model parameters payload.parameters.${parameterName}`);
    }
    for (const [categoryName, categoryValue] of Object.entries(rawCategories)) {
        categories[categoryName] = decodeCategory(categoryValue, `Model parameters payload.categories.${categoryName}`);
    }
    const universalId = optionalString(record, 'universal_id', 'Model parameters payload');
    const plugin = optionalString(record, 'plugin', 'Model parameters payload');
    const sourceModelId = optionalString(record, 'source_model_id', 'Model parameters payload');
    const parameterVersion = record['parameter_version'];
    if (parameterVersion !== undefined && (!isNumber(parameterVersion) || !Number.isInteger(parameterVersion) || parameterVersion < 0)) {
        throw new TypeError('Model parameters payload.parameter_version must be a non-negative integer.');
    }
    return { universalId, plugin, sourceModelId, parameterVersion, parameters, categories };
};

const serializeDefinition = (definition: ParameterDefinition): JsonObject => {
    const output: JsonObject = {};
    if (definition.displayName !== undefined) output['display_name'] = definition.displayName;
    if (definition.category !== undefined) output['category'] = definition.category;
    if (definition.group !== undefined) output['group'] = definition.group;
    if (definition.description !== undefined) output['description'] = definition.description;
    if (definition.aliases !== undefined) output['aliases'] = definition.aliases;
    if (definition.linkedParameterName !== undefined) output['linked_parameter_name'] = definition.linkedParameterName;
    if (definition.isStandardizedAlias !== undefined) output['is_standardized_alias'] = definition.isStandardizedAlias;
    if (definition.requiresReload !== undefined) output['requires_reload'] = definition.requiresReload;
    if (definition.default !== undefined) output['default'] = definition.default;
    if (definition.hasDefault !== undefined) output['has_default'] = definition.hasDefault;
    if (definition.type !== undefined) output['type'] = definition.type;
    if (definition.itemType !== undefined) output['item_type'] = definition.itemType;
    if (definition.minimum !== undefined) output['minimum'] = definition.minimum;
    if (definition.maximum !== undefined) output['maximum'] = definition.maximum;
    if (definition.numericStringMinimum !== undefined) output['numeric_string_minimum'] = definition.numericStringMinimum;
    if (definition.numericStringMaximum !== undefined) output['numeric_string_maximum'] = definition.numericStringMaximum;
    if (definition.valueCount !== undefined) output['value_count'] = definition.valueCount;
    if (definition.choices !== undefined) output['choices'] = definition.choices;
    return output;
};

const serializeParameter = (parameter: Parameter): JsonObject => {
    const output: JsonObject = {};
    if (parameter.definition !== undefined) output['definition'] = serializeDefinition(parameter.definition);
    if (parameter.currentValue !== undefined) output['current_value'] = parameter.currentValue;
    if (parameter.isCustom !== undefined) output['is_custom'] = parameter.isCustom;
    if (parameter.hasDefault !== undefined) output['has_default'] = parameter.hasDefault;
    return output;
};

const serializeCategory = (category: ParameterCategory): JsonValue => {
    if (isString(category)) return category;
    const output: JsonObject = {};
    if (category.title !== undefined) output['title'] = category.title;
    if (category.description !== undefined) output['description'] = category.description;
    return output;
};

const serializeModelDetailParameterPayload = (payload: ModelDetailParametersData): JsonObject => {
    const parameters: JsonObject = {};
    const categories: JsonObject = {};
    for (const [parameterName, parameter] of Object.entries(payload.parameters ?? {})) parameters[parameterName] = serializeParameter(parameter);
    for (const [categoryName, category] of Object.entries(payload.categories ?? {})) categories[categoryName] = serializeCategory(category);
    const output: JsonObject = { parameters, categories };
    if (payload.universalId !== undefined) output['universal_id'] = payload.universalId;
    if (payload.plugin !== undefined) output['plugin'] = payload.plugin;
    if (payload.sourceModelId !== undefined) output['source_model_id'] = payload.sourceModelId;
    if (payload.parameterVersion !== undefined) output['parameter_version'] = payload.parameterVersion;
    return output;
};

export { decodeModelDetailParameterPayload, serializeModelDetailParameterPayload };
