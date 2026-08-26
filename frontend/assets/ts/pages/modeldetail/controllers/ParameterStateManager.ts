/* SoAI - Model detail page control layer parameter state manager [frontend/assets/ts/pages/modeldetail/controllers/ParameterStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { deepClone } from '@core/primitives/clone.ts';
import { hasOwn, isArray, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import { filterNonEmptyStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import type { Parameter, ParameterCategory, ParameterCollection, ParameterDefinition, ParametersPayload } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { areValuesEqual, sanitizeParameterValue } from '@pages/modeldetail/mappers/parameterValueNormalization.ts';

interface ParameterMetadata {
    category: string;
    group: string;
    keywords: string[];
    linkedParameterName: string | null;
}

interface SetValueResult {
    parameter: Parameter;
    isCustomized: boolean;
    isModified: boolean;
    changedKeys: string[];
}

const buildKeywords = (key: string, definition: ParameterDefinition = {}): string[] => {
    const aliases = isArray(definition.aliases) ? definition.aliases : [];
    const tokens: JsonValue[] = [key, definition.displayName ?? null, definition.description ?? null, ...aliases];
    return filterNonEmptyStringArrayValue(tokens).map((token) => token.toLowerCase());
};

const isCustomizedValue = (parameter: Parameter | null | undefined, valueOverride?: JsonValue): boolean => {
    if (parameter?.isCustom !== undefined && valueOverride === undefined) {
        return parameter.isCustom;
    }
    const definition = parameter?.definition && isObject(parameter.definition) ? parameter.definition : {};
    const hasDefault = parameter?.hasDefault ?? definition.hasDefault ?? 'default' in definition;
    const sanitized = sanitizeParameterValue(parameter, valueOverride ?? null, { treatDefaultAsNull: false });
    const effectiveValue = isNullOrUndefined(sanitized) && hasDefault ? definition.default : sanitized;
    if (hasDefault) {
        return !areValuesEqual(effectiveValue, definition.default);
    }
    if (isArray(sanitized)) {
        return sanitized.some((item) => item !== '' && !isNullOrUndefined(item));
    }
    if (sanitized && isObject(sanitized)) {
        return Object.keys(sanitized).length > 0;
    }
    return !isNullOrUndefined(sanitized) && sanitized !== '';
};

class ParameterStateManager {
    parametersData: ParametersPayload = {};
    parameters: ParameterCollection = {};
    originalParameters: ParameterCollection = {};
    categories: Record<string, ParameterCategory> = {};
    customizedParameters: Set<string> = new Set();
    metadata: Map<string, ParameterMetadata> = new Map();

    reset(): void {
        this.parametersData = {};
        this.parameters = {};
        this.originalParameters = {};
        this.categories = {};
        this.customizedParameters = new Set();
        this.metadata = new Map();
    }

    applyPayload(payload: ParametersPayload = {}): void {
        this.reset();
        this.parametersData = payload ?? {};
        this.parameters = this.parametersData.parameters ?? {};
        this.categories = this.parametersData.categories ?? {};
        Object.entries(this.parameters).forEach(([key, parameter]) => {
            if (!isObject(parameter)) return;
            const rawCurrentValue = hasOwn(parameter, 'currentValue') ? parameter.currentValue : undefined;
            const sanitized = sanitizeParameterValue(parameter, rawCurrentValue, { treatDefaultAsNull: false });
            parameter.currentValue = sanitized;
            const definition = parameter.definition && isObject(parameter.definition) ? parameter.definition : {};
            const linkedParameterNameCandidate = definition.linkedParameterName;
            const linkedParameterName = isString(linkedParameterNameCandidate) && linkedParameterNameCandidate.trim().length > 0 ? linkedParameterNameCandidate : null;
            if (linkedParameterName) {
                definition.linkedParameterName = linkedParameterName;
            }
            const hasDefault = parameter.hasDefault ?? definition.hasDefault;
            if (hasDefault !== undefined) {
                parameter.hasDefault = Boolean(hasDefault);
                definition.hasDefault = Boolean(hasDefault);
            }
            const displayValue = parameter.currentValue ?? definition.default ?? null;
            const isCustom = parameter.isCustom ?? isCustomizedValue(parameter, displayValue);
            if (isCustom) this.customizedParameters.add(key);
            this.metadata.set(key, {
                category: definition.category || 'other',
                group: definition.group || 'unknown',
                keywords: buildKeywords(key, definition),
                linkedParameterName
            });
        });
        this.originalParameters = deepClone(this.parameters);
    }

    getParameterKeys(): string[] {
        return Object.keys(this.parameters);
    }

    getParameter(parameterKey: string): Parameter | undefined {
        return this.parameters[parameterKey];
    }

    getOriginalParameter(parameterKey: string): Parameter | undefined {
        return this.originalParameters[parameterKey];
    }

    getMetadata(parameterKey: string): ParameterMetadata | undefined {
        return this.metadata.get(parameterKey);
    }

    setParameterValue(parameterKey: string, value: JsonValue): SetValueResult | null {
        const parameter = this.getParameter(parameterKey);
        if (!parameter) return null;
        const sanitized = sanitizeParameterValue(parameter, value, {
            preserveEmptyArrayItems: true,
            treatDefaultAsNull: false
        });
        parameter.currentValue = sanitized;
        const isCustomized = this.updateCustomization(parameterKey);
        const isModified = this.updateModification(parameterKey);
        const changedKeys: string[] = [parameterKey];
        const linkedParameterName = this.metadata.get(parameterKey)?.linkedParameterName;
        if (linkedParameterName) {
            const linkedParameter = this.getParameter(linkedParameterName);
            if (linkedParameter) {
                linkedParameter.currentValue = deepClone(sanitized);
                this.updateCustomization(linkedParameterName);
                changedKeys.push(linkedParameterName);
            }
        }
        return { parameter, isCustomized, isModified, changedKeys };
    }

    getLinkedParameterKey(parameterKey: string): string | null {
        return this.metadata.get(parameterKey)?.linkedParameterName ?? null;
    }

    updateCustomization(parameterKey: string, valueOverride?: JsonValue): boolean {
        const parameter = this.getParameter(parameterKey);
        if (!parameter) {
            this.customizedParameters.delete(parameterKey);
            return false;
        }
        const isCustomized = isCustomizedValue(parameter, valueOverride !== undefined ? valueOverride : (parameter.currentValue ?? null));
        if (isCustomized) this.customizedParameters.add(parameterKey);
        else this.customizedParameters.delete(parameterKey);
        return isCustomized;
    }

    isParameterCustomized(parameterKey: string): boolean {
        return this.customizedParameters.has(parameterKey);
    }

    updateModification(parameterKey: string, overrideValue?: JsonValue): boolean {
        const parameter = this.getParameter(parameterKey);
        if (!parameter) {
            return false;
        }
        const originalParameter = this.getOriginalParameter(parameterKey);
        const currentValue = overrideValue !== undefined ? sanitizeParameterValue(parameter, overrideValue, { treatDefaultAsNull: false }) : sanitizeParameterValue(parameter, parameter.currentValue ?? null, { treatDefaultAsNull: false });
        const originalValue = originalParameter ? sanitizeParameterValue(originalParameter, originalParameter.currentValue ?? null, { treatDefaultAsNull: false }) : undefined;
        return !areValuesEqual(currentValue, originalValue);
    }

    isParameterModified(parameterKey: string): boolean {
        return this.updateModification(parameterKey);
    }

    resetParameter(parameterKey: string): JsonValue {
        const originalParameter = this.getOriginalParameter(parameterKey);
        if (!originalParameter) return null;
        const parameter = this.getParameter(parameterKey);
        const clonedValue = deepClone(originalParameter.currentValue);
        if (parameter) parameter.currentValue = clonedValue;
        this.updateCustomization(parameterKey, clonedValue);
        const linkedParameterName = this.metadata.get(parameterKey)?.linkedParameterName;
        if (linkedParameterName) {
            const linkedOriginal = this.getOriginalParameter(linkedParameterName);
            const linkedParameter = this.getParameter(linkedParameterName);
            if (linkedParameter && linkedOriginal) {
                const linkedValue = deepClone(linkedOriginal.currentValue);
                linkedParameter.currentValue = linkedValue;
                this.updateCustomization(linkedParameterName, linkedValue);
            }
        }
        return clonedValue ?? null;
    }

    getCustomizedKeys(): string[] {
        return Array.from(this.customizedParameters);
    }

    get count(): number {
        return this.getParameterKeys().length;
    }

    commit(): void {
        this.originalParameters = deepClone(this.parameters);
    }
}

export { ParameterStateManager };
export type { ParameterMetadata };
