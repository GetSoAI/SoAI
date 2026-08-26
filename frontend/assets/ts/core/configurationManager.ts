/* SoAI - Shared frontend configuration manager [frontend/assets/ts/core/configurationManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneJsonObject } from '@core/primitives/clone.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { mergeJsonObjectPatch } from '@core/types/jsonObjectPatch.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type Validator = (value: JsonValue, path: string) => boolean | string;
type ChangeHandler = (data: { path: string; value: JsonValue; hasChanges: boolean }) => void;

const setValueByPath = (object: JsonObject, path: string, value: JsonValue): void => {
    const keys = path.split('.');
    if (keys.length === 0) {
        throw new Error('Path must not be empty');
    }
    let target: JsonObject = object;
    for (let index = 0; index < keys.length - 1; index += 1) {
        const key = keys[index];
        if (!key) {
            throw new Error(`Path contains an empty key segment: "${path}"`);
        }
        const existing = target[key];
        if (isJsonObject(existing)) {
            target = existing;
            continue;
        }
        const created: JsonObject = {};
        target[key] = created;
        target = created;
    }
    const lastKey = keys[keys.length - 1];
    if (!lastKey) {
        throw new Error(`Path must end with a non-empty key: "${path}"`);
    }
    target[lastKey] = value;
};

const getValueByPath = (object: JsonObject, path: string): JsonValue => {
    const keys = path.split('.');
    if (keys.length === 0) {
        throw new Error('Path must not be empty');
    }
    let current: JsonValue = object;
    for (const key of keys) {
        if (!key) {
            throw new Error(`Path contains an empty key segment: "${path}"`);
        }
        if (!isJsonObject(current)) {
            throw new Error(`Cannot access property '${key}' of ${String(current)} at path '${path}'`);
        }
        if (!(key in current)) {
            throw new Error(`Missing property '${key}' at path '${path}'`);
        }
        const next: JsonValue | undefined = current[key];
        if (next === undefined) {
            throw new Error(`Missing property '${key}' at path '${path}'`);
        }
        current = next;
    }
    return current;
};

const areValuesEqual = (firstValue: JsonValue | undefined, secondValue: JsonValue | undefined): boolean => {
    if (firstValue === secondValue) {
        return true;
    }
    if (firstValue === null || secondValue === null || firstValue === undefined || secondValue === undefined) {
        return firstValue === secondValue;
    }
    if (Array.isArray(firstValue)) {
        if (!Array.isArray(secondValue)) return false;
        if (firstValue.length !== secondValue.length) return false;
        for (let index = 0; index < firstValue.length; index += 1) {
            if (!areValuesEqual(firstValue[index], secondValue[index])) return false;
        }
        return true;
    }
    if (Array.isArray(secondValue)) {
        return false;
    }
    if (typeof firstValue !== typeof secondValue) {
        return false;
    }
    if (!isJsonObject(firstValue) || !isJsonObject(secondValue)) {
        return false;
    }
    const keysA = Object.keys(firstValue);
    const keysB = Object.keys(secondValue);
    if (keysA.length !== keysB.length) return false;
    for (const key of keysA) {
        if (!(key in secondValue)) return false;
        if (!areValuesEqual(firstValue[key], secondValue[key])) return false;
    }
    return true;
};

class ConfigurationManager {
    #originalData: JsonObject | null = null;
    #currentData: JsonObject | null = null;
    #hasChanges = false;
    #validators = new Map<string, Validator>();
    #changeHandlers = new Set<ChangeHandler>();

    constructor() {}

    initialize(data: JsonObject): this {
        if (!isJsonObject(data)) {
            throw new Error('Configuration data must be an object');
        }
        this.#originalData = cloneJsonObject(data);
        this.#currentData = cloneJsonObject(data);
        this.#hasChanges = false;
        return this;
    }

    updateValue(path: string, value: JsonValue): boolean {
        if (!path) {
            throw new Error('Path is required');
        }
        const current = this.#requireCurrentData();
        setValueByPath(current, path, value);
        this.#hasChanges = !areValuesEqual(this.#currentData, this.#originalData);
        const validator = this.#validators.get(path);
        if (validator) {
            const result = validator(value, path);
            if (result !== true) {
                throw new Error(isString(result) ? result : 'Validation failed');
            }
        }
        this.#notifyChange(path, value);
        return this.#hasChanges;
    }

    getValue(path: string): JsonValue {
        if (!path) {
            throw new Error('Path is required');
        }
        const current = this.#requireCurrentData();
        return getValueByPath(current, path);
    }

    getValueByPath(target: JsonValue, path: string): JsonValue {
        if (!path) {
            throw new Error('Path is required');
        }
        if (!isJsonObject(target)) {
            throw new Error('Target must be an object');
        }
        return getValueByPath(target, path);
    }

    areValuesEqual(firstValue: JsonValue | undefined, secondValue: JsonValue | undefined): boolean {
        return areValuesEqual(firstValue, secondValue);
    }

    resetChanges(): this {
        const original = this.#requireOriginalData();
        this.#currentData = cloneJsonObject(original);
        this.#hasChanges = false;
        return this;
    }

    commitChanges(): this {
        const current = this.#requireCurrentData();
        this.#originalData = cloneJsonObject(current);
        this.#hasChanges = false;
        return this;
    }

    applyCommittedPatch(patch: JsonObject): this {
        const original = this.#requireOriginalData();
        const current = this.#requireCurrentData();
        this.#originalData = mergeJsonObjectPatch(original, patch);
        this.#currentData = mergeJsonObjectPatch(current, patch);
        this.#hasChanges = !areValuesEqual(this.#currentData, this.#originalData);
        return this;
    }

    addValidator(path: string, validator: Validator): this {
        if (!path) {
            throw new Error('Path is required');
        }
        if (!isFunction(validator)) {
            throw new Error('Validator must be a function');
        }
        this.#validators.set(path, validator);
        return this;
    }

    validateAll(): this {
        const errors: Array<{ path: string; message: string }> = [];
        for (const [path, validator] of this.#validators.entries()) {
            const value = this.getValue(path);
            const result = validator(value, path);
            if (result !== true) {
                errors.push({ path, message: isString(result) ? result : 'Validation failed' });
            }
        }
        if (errors.length > 0) {
            throw new Error(`Validation failed: ${errors.map((entry) => `${entry.path}: ${entry.message}`).join(', ')}`);
        }
        return this;
    }

    onChange(handler: ChangeHandler): () => void {
        if (!isFunction(handler)) {
            throw new Error('Handler must be a function');
        }
        this.#changeHandlers.add(handler);
        return () => this.#changeHandlers.delete(handler);
    }

    #notifyChange(path: string, value: JsonValue): void {
        for (const handler of this.#changeHandlers) {
            handler({ path, value, hasChanges: this.#hasChanges });
        }
    }

    get hasChanges(): boolean {
        return this.#hasChanges;
    }

    get originalData(): JsonObject {
        return cloneJsonObject(this.#requireOriginalData());
    }

    get currentData(): JsonObject {
        return cloneJsonObject(this.#requireCurrentData());
    }

    #requireOriginalData(): JsonObject {
        if (!this.#originalData) {
            throw new Error('ConfigurationManager is not initialized');
        }
        return this.#originalData;
    }

    #requireCurrentData(): JsonObject {
        if (!this.#currentData) {
            throw new Error('ConfigurationManager is not initialized');
        }
        return this.#currentData;
    }
}

export { ConfigurationManager };
