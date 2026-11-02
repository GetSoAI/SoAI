/* SoAI - Shared frontend configuration manager [frontend/assets/ts/core/configurationManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneJsonObject, cloneJsonValue } from '@core/primitives/clone.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import { hasOwn, isFunction, isString } from '@core/typeGuards.ts';
import { mergeJsonObjectPatch, rebaseJsonObjectChanges } from '@core/types/jsonObjectPatch.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createAbortError } from '@core/errors/abort.ts';

type Validator = (value: JsonValue, path: string) => boolean | string;
type ChangeHandler = (data: { path: string; value: JsonValue; hasChanges: boolean }) => void;

const parseConfigurationPath = (path: string): { parents: string[]; last: string } => {
    const segments = path.split('.');
    if (segments.some((segment) => !segment || segment === '__proto__')) throw new Error(`Configuration path contains an invalid key: "${path}"`);
    const last = segments.pop();
    if (!last) throw new Error('Path must not be empty');
    return { parents: segments, last };
};

const setValueByPath = (object: JsonObject, keys: { parents: string[]; last: string }, value: JsonValue): void => {
    let target = object;
    for (const key of keys.parents) {
        const existing = hasOwn(target, key) ? target[key] : undefined;
        if (isJsonObject(existing)) target = existing;
        else {
            const created: JsonObject = {};
            target[key] = created;
            target = created;
        }
    }
    target[keys.last] = value;
};

const getValueByPath = (object: JsonObject, path: string): JsonValue => {
    const keys = parseConfigurationPath(path);
    let current: JsonValue = object;
    for (const key of [...keys.parents, keys.last]) {
        if (!isJsonObject(current)) throw new Error(`Cannot access property '${key}' of ${String(current)} at path '${path}'`);
        if (!hasOwn(current, key)) throw new Error(`Missing property '${key}' at path '${path}'`);
        const next: JsonValue | undefined = current[key];
        if (next === undefined) throw new Error(`Missing property '${key}' at path '${path}'`);
        current = next;
    }
    return current;
};

const areValuesEqual = (firstValue: JsonValue | undefined, secondValue: JsonValue | undefined): boolean => deepEqual(firstValue, secondValue, { nullishEqual: false });

class ConfigurationManager {
    #originalData: JsonObject | null = null;
    #currentData: JsonObject | null = null;
    #hasChanges = false;
    #protectionRevision = 0;
    #validators = new Map<string, Validator>();
    #changeHandlers = new Set<ChangeHandler>();
    readonly #canMutate: () => boolean;

    constructor(canMutate: () => boolean = () => true) {
        this.#canMutate = canMutate;
    }

    initialize(data: JsonObject): this {
        if (!isJsonObject(data)) {
            throw new Error('Configuration data must be an object');
        }
        const original = cloneJsonObject(data);
        const current = cloneJsonObject(data);
        this.#originalData = original;
        this.#currentData = current;
        this.#hasChanges = false;
        this.#protectionRevision += 1;
        return this;
    }

    updateValue(path: string, value: JsonValue): boolean {
        if (!this.#canMutate()) throw createAbortError('Configuration draft mutation is not admitted');
        if (!path) {
            throw new Error('Path is required');
        }
        const keys = parseConfigurationPath(path);
        const current = this.#requireCurrentData();
        const revision = this.#protectionRevision;
        const proposed = cloneJsonValue(value);
        const updated = cloneJsonObject(current);
        setValueByPath(updated, keys, proposed);
        const validator = this.#validators.get(path);
        if (validator) {
            const result = validator(cloneJsonValue(proposed), path);
            if (result !== true) {
                throw new Error(isString(result) ? result : 'Validation failed');
            }
        }
        if (!this.#canMutate()) throw createAbortError('Configuration draft mutation is not admitted');
        if (this.#currentData !== current || this.#protectionRevision !== revision) throw new Error('Configuration changed during draft validation');
        this.#currentData = updated;
        this.#hasChanges = !areValuesEqual(updated, this.#originalData);
        this.#protectionRevision += 1;
        this.#notifyChange(path, proposed);
        return this.#hasChanges;
    }

    getValue(path: string): JsonValue {
        if (!path) {
            throw new Error('Path is required');
        }
        const current = this.#requireCurrentData();
        return cloneJsonValue(getValueByPath(current, path));
    }

    getOriginalValue(path: string): JsonValue {
        if (!path) {
            throw new Error('Path is required');
        }
        return cloneJsonValue(getValueByPath(this.#requireOriginalData(), path));
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
        if (!this.#canMutate()) throw createAbortError('Configuration draft mutation is not admitted');
        const original = this.#requireOriginalData();
        this.#currentData = cloneJsonObject(original);
        this.#hasChanges = false;
        this.#protectionRevision += 1;
        return this;
    }

    commitChanges(snapshot?: JsonObject): this {
        const current = this.#requireCurrentData();
        this.#originalData = cloneJsonObject(snapshot ?? current);
        this.#hasChanges = !areValuesEqual(current, this.#originalData);
        this.#protectionRevision += 1;
        return this;
    }

    applyCommittedPatch(patch: JsonObject): this {
        const original = this.#requireOriginalData();
        const current = this.#requireCurrentData();
        const committed = cloneJsonObject(patch);
        const nextOriginal = mergeJsonObjectPatch(original, committed);
        const nextCurrent = mergeJsonObjectPatch(current, committed);
        this.#originalData = nextOriginal;
        this.#currentData = nextCurrent;
        this.#hasChanges = !areValuesEqual(this.#currentData, this.#originalData);
        this.#protectionRevision += 1;
        return this;
    }

    commitBaselinePatch(patch: JsonObject, submitted?: JsonObject): this {
        const committed = cloneJsonObject(patch);
        const original = mergeJsonObjectPatch(this.#requireOriginalData(), committed);
        const current = this.#requireCurrentData();
        const updated = submitted ? rebaseJsonObjectChanges(submitted, current, mergeJsonObjectPatch(current, committed)) : current;
        this.#originalData = original;
        this.#currentData = updated;
        this.#hasChanges = !areValuesEqual(this.#requireCurrentData(), this.#originalData);
        this.#protectionRevision += 1;
        return this;
    }

    mergeRemotePatch(patch: JsonObject): this {
        const original = this.#requireOriginalData();
        const latest = mergeJsonObjectPatch(original, cloneJsonObject(patch));
        this.#currentData = rebaseJsonObjectChanges(original, this.#requireCurrentData(), latest);
        this.#originalData = latest;
        this.#hasChanges = !areValuesEqual(this.#currentData, this.#originalData);
        this.#protectionRevision += 1;
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
        this.#protectionRevision += 1;
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
        const revision = this.#protectionRevision;
        for (const handler of [...this.#changeHandlers]) {
            if (revision !== this.#protectionRevision) break;
            if (!this.#changeHandlers.has(handler)) continue;
            try {
                handler({ path, value: cloneJsonValue(value), hasChanges: this.#hasChanges });
            } catch (error) {
                errorHandler.error('ConfigurationManager', 'Configuration draft observer failed', ensureError(error));
            }
        }
    }

    get protectionRevision(): number {
        return this.#protectionRevision;
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
