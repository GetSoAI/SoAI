/* SoAI - Model detail page control layer parameter state manager [frontend/assets/ts/pages/modeldetail/controllers/ParameterStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError } from '@core/errors/abort.ts';
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
    #protectionRevision = 0;
    readonly #canMutate: () => boolean;
    #parametersData: ParametersPayload = {};
    #parameters: ParameterCollection = {};
    #originalParameters: ParameterCollection = {};
    #categories: Record<string, ParameterCategory> = {};
    #customizedParameters: Set<string> = new Set();
    #metadata: Map<string, ParameterMetadata> = new Map();

    constructor(canMutate: () => boolean = () => true) {
        this.#canMutate = canMutate;
    }

    get protectionRevision(): number {
        return this.#protectionRevision;
    }

    get parametersData(): ParametersPayload {
        return deepClone(this.#parametersData);
    }

    get parameters(): ParameterCollection {
        return deepClone(this.#parameters);
    }

    get originalParameters(): ParameterCollection {
        return deepClone(this.#originalParameters);
    }

    get categories(): Record<string, ParameterCategory> {
        return deepClone(this.#categories);
    }

    get customizedParameters(): Set<string> {
        return new Set(this.#customizedParameters);
    }

    get metadata(): Map<string, ParameterMetadata> {
        return new Map([...this.#metadata].map(([key, value]) => [key, deepClone(value)]));
    }

    reset(): void {
        this.#protectionRevision += 1;
        this.#parametersData = {};
        this.#parameters = {};
        this.#originalParameters = {};
        this.#categories = {};
        this.#customizedParameters = new Set();
        this.#metadata = new Map();
    }

    applyPayload(payload: ParametersPayload = {}): void {
        const snapshot = deepClone(payload);
        const parameters = snapshot.parameters ?? {};
        const customized = new Set<string>();
        const metadata = new Map<string, ParameterMetadata>();
        Object.entries(parameters).forEach(([key, parameter]) => {
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
            if (isCustom) customized.add(key);
            metadata.set(key, {
                category: definition.category || 'other',
                group: definition.group || 'unknown',
                keywords: buildKeywords(key, definition),
                linkedParameterName
            });
        });
        const original = deepClone(parameters);
        this.#protectionRevision += 1;
        this.#parametersData = snapshot;
        this.#parameters = parameters;
        this.#categories = snapshot.categories ?? {};
        this.#customizedParameters = customized;
        this.#metadata = metadata;
        this.#originalParameters = original;
    }

    mergePayload(payload: ParametersPayload, isProtected: (key: string) => boolean): string[] {
        const previous = this.#parameters;
        const revision = this.#protectionRevision;
        const protectedKeys = new Set(this.getParameterKeys().filter((key) => isProtected(key) || this.isParameterModified(key)));
        let protectedCount = -1;
        while (protectedCount !== protectedKeys.size) {
            protectedCount = protectedKeys.size;
            for (const [key, metadata] of this.#metadata) {
                const linked = metadata.linkedParameterName;
                if (linked && (protectedKeys.has(key) || protectedKeys.has(linked))) {
                    protectedKeys.add(key);
                    protectedKeys.add(linked);
                }
            }
        }
        if (revision !== this.#protectionRevision) throw createAbortError('Parameter protection changed during reconciliation');
        this.applyPayload(payload);
        for (const key of protectedKeys) {
            const parameter = this.#parameters[key];
            const retained = previous[key];
            if (parameter && retained) {
                parameter.currentValue = deepClone(retained.currentValue);
                this.updateCustomization(key);
            }
        }
        return this.getParameterKeys().filter((key) => !protectedKeys.has(key) && !areValuesEqual(previous[key]?.currentValue, this.#parameters[key]?.currentValue));
    }

    getParameterKeys(): string[] {
        return Object.keys(this.#parameters);
    }

    getParameter(parameterKey: string): Parameter | undefined {
        const parameter = this.#parameters[parameterKey];
        return parameter ? deepClone(parameter) : undefined;
    }

    getOriginalParameter(parameterKey: string): Parameter | undefined {
        const parameter = this.#originalParameters[parameterKey];
        return parameter ? deepClone(parameter) : undefined;
    }

    getMetadata(parameterKey: string): ParameterMetadata | undefined {
        const metadata = this.#metadata.get(parameterKey);
        return metadata ? deepClone(metadata) : undefined;
    }

    setParameterValue(parameterKey: string, value: JsonValue): SetValueResult | null {
        if (!this.#canMutate()) throw createAbortError('Parameter draft mutation is not admitted');
        const parameter = this.#parameters[parameterKey];
        if (!parameter) return null;
        const sanitized = deepClone(
            sanitizeParameterValue(parameter, value, {
                preserveEmptyArrayItems: true,
                treatDefaultAsNull: false
            })
        );
        this.#protectionRevision += 1;
        parameter.currentValue = sanitized;
        const isCustomized = this.updateCustomization(parameterKey);
        const isModified = this.updateModification(parameterKey);
        const changedKeys: string[] = [parameterKey];
        const linkedParameterName = this.#metadata.get(parameterKey)?.linkedParameterName;
        if (linkedParameterName) {
            const linkedParameter = this.#parameters[linkedParameterName];
            if (linkedParameter) {
                linkedParameter.currentValue = deepClone(sanitized);
                this.updateCustomization(linkedParameterName);
                changedKeys.push(linkedParameterName);
            }
        }
        return { parameter: deepClone(parameter), isCustomized, isModified, changedKeys };
    }

    getLinkedParameterKey(parameterKey: string): string | null {
        return this.#metadata.get(parameterKey)?.linkedParameterName ?? null;
    }

    updateCustomization(parameterKey: string, valueOverride?: JsonValue): boolean {
        const parameter = this.#parameters[parameterKey];
        if (!parameter) {
            this.#customizedParameters.delete(parameterKey);
            return false;
        }
        const isCustomized = isCustomizedValue(parameter, valueOverride !== undefined ? valueOverride : (parameter.currentValue ?? null));
        if (isCustomized) this.#customizedParameters.add(parameterKey);
        else this.#customizedParameters.delete(parameterKey);
        return isCustomized;
    }

    isParameterCustomized(parameterKey: string): boolean {
        return this.#customizedParameters.has(parameterKey);
    }

    updateModification(parameterKey: string, overrideValue?: JsonValue): boolean {
        const parameter = this.#parameters[parameterKey];
        if (!parameter) {
            return false;
        }
        const originalParameter = this.#originalParameters[parameterKey];
        const currentValue = sanitizeParameterValue(parameter, overrideValue !== undefined ? overrideValue : (parameter.currentValue ?? null));
        const originalValue = originalParameter ? sanitizeParameterValue(originalParameter, originalParameter.currentValue ?? null) : undefined;
        return !areValuesEqual(currentValue, originalValue);
    }

    isParameterModified(parameterKey: string): boolean {
        return this.updateModification(parameterKey);
    }

    resetParameter(parameterKey: string): JsonValue {
        if (!this.#canMutate()) throw createAbortError('Parameter draft mutation is not admitted');
        const originalParameter = this.#originalParameters[parameterKey];
        if (!originalParameter) return null;
        const parameter = this.#parameters[parameterKey];
        const clonedValue = deepClone(originalParameter.currentValue);
        this.#protectionRevision += 1;
        if (parameter) parameter.currentValue = clonedValue;
        this.updateCustomization(parameterKey, clonedValue);
        const linkedParameterName = this.#metadata.get(parameterKey)?.linkedParameterName;
        if (linkedParameterName) {
            const linkedOriginal = this.#originalParameters[linkedParameterName];
            const linkedParameter = this.#parameters[linkedParameterName];
            if (linkedParameter && linkedOriginal) {
                const linkedValue = deepClone(linkedOriginal.currentValue);
                linkedParameter.currentValue = linkedValue;
                this.updateCustomization(linkedParameterName, linkedValue);
            }
        }
        return deepClone(clonedValue) ?? null;
    }

    getCustomizedKeys(): string[] {
        return Array.from(this.#customizedParameters);
    }

    get count(): number {
        return this.getParameterKeys().length;
    }

    commit(submittedValues: Record<string, JsonValue>): void {
        const submitted = deepClone(submittedValues);
        this.#protectionRevision += 1;
        for (const [key, value] of Object.entries(submitted)) {
            const original = this.#originalParameters[key];
            if (original) original.currentValue = deepClone(value);
        }
    }
}

export { ParameterStateManager };
export type { ParameterMetadata };
