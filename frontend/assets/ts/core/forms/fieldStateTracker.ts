/* SoAI - Shared forms field state tracker [frontend/assets/ts/core/forms/fieldStateTracker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireFieldSurface, setFieldSurfaceInvalid, setFieldSurfaceModified } from '@core/forms/fieldSurface.ts';
import { isArray, isFunction, isNullOrUndefined } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface FieldStateChangeEvent {
    key: string;
    isModified: boolean;
    isInvalid: boolean;
    element: Element | null;
    currentValue: JsonValue | null | undefined;
    originalValue: JsonValue | null | undefined;
}

interface FieldStateTrackerOptions {
    getElement: (key: string) => Element | null;
    getElements?: ((key: string) => Element[]) | null | undefined;
    getCurrentValue?: ((key: string) => JsonValue | null | undefined) | null | undefined;
    getOriginalValue?: ((key: string) => JsonValue | null | undefined) | null | undefined;
    comparator?: ((current: JsonValue | null | undefined, original: JsonValue | null | undefined, key: string) => boolean) | null | undefined;
    onStateChange?: ((event: FieldStateChangeEvent) => void) | null | undefined;
}

interface FieldStateUpdateOptions {
    currentValue?: JsonValue | null | undefined;
    originalValue?: JsonValue | null | undefined;
}

interface FieldTargets {
    elements: Element[];
    surfaces: Set<Element>;
}

interface FieldSurfaceState {
    modifiedKeys: Set<string>;
    invalidKeys: Set<string>;
}

const safeBoolean = (value: boolean | undefined): boolean => value === true;

class FieldStateTracker {
    getElement: (key: string) => Element | null;
    getElements: ((key: string) => Element[]) | null;
    getCurrentValue: ((key: string) => JsonValue | null | undefined) | null;
    getOriginalValue: ((key: string) => JsonValue | null | undefined) | null;
    comparator: (current: JsonValue | null | undefined, original: JsonValue | null | undefined, key: string) => boolean;
    onStateChange: ((event: FieldStateChangeEvent) => void) | null;
    trackedKeys: Set<string>;
    modifiedStates: Map<string, boolean>;
    invalidMessages: Map<string, string>;
    keySurfaces: Map<string, Set<Element>>;
    surfaceStates: WeakMap<Element, FieldSurfaceState>;

    constructor(options: FieldStateTrackerOptions) {
        const { getElement, getElements = null, getCurrentValue = null, getOriginalValue = null, comparator = null, onStateChange = null } = options;
        if (!isFunction(getElement)) {
            throw new Error('FieldStateTracker requires a getElement(key) resolver');
        }
        this.getElement = getElement;
        this.getElements = isFunction(getElements) ? getElements : null;
        this.getCurrentValue = isFunction(getCurrentValue) ? getCurrentValue : null;
        this.getOriginalValue = isFunction(getOriginalValue) ? getOriginalValue : null;
        this.comparator = isFunction(comparator) ? comparator : (current, original) => current === original;
        this.onStateChange = isFunction(onStateChange) ? onStateChange : null;
        this.trackedKeys = new Set();
        this.modifiedStates = new Map();
        this.invalidMessages = new Map();
        this.keySurfaces = new Map();
        this.surfaceStates = new WeakMap();
    }

    update(key: string, { currentValue, originalValue }: FieldStateUpdateOptions = {}): boolean {
        if (isNullOrUndefined(key)) {
            return false;
        }
        this.trackedKeys.add(key);
        const targets = this.resolveTargets(key);
        const targetElement = targets.elements[0] ?? null;
        const current = currentValue !== undefined ? currentValue : this.getCurrentValue ? this.getCurrentValue(key) : undefined;
        const original = originalValue !== undefined ? originalValue : this.getOriginalValue ? this.getOriginalValue(key) : undefined;
        const isModified = !this.comparator(current, original, key);
        const previousModified = this.modifiedStates.get(key);
        this.modifiedStates.set(key, isModified);
        this.applyKeyStateToSurfaces(key, targets.surfaces);
        this.emitStateChange(key, targetElement, current, original, previousModified !== isModified);
        return isModified;
    }

    setModified(key: string, isModified: boolean): void {
        if (isNullOrUndefined(key)) {
            return;
        }
        this.trackedKeys.add(key);
        const previousModified = this.modifiedStates.get(key);
        this.modifiedStates.set(key, isModified);
        const targets = this.resolveTargets(key);
        this.applyKeyStateToSurfaces(key, targets.surfaces);
        const element = targets.elements[0] ?? null;
        this.emitStateChange(key, element, undefined, undefined, previousModified !== isModified);
    }

    setInvalid(key: string, message: string | null): void {
        if (isNullOrUndefined(key)) {
            return;
        }
        this.trackedKeys.add(key);
        const wasInvalid = this.invalidMessages.has(key);
        if (message && message.trim().length > 0) {
            this.invalidMessages.set(key, message);
        } else {
            this.invalidMessages.delete(key);
        }
        const targets = this.resolveTargets(key);
        this.applyKeyStateToSurfaces(key, targets.surfaces);
        const element = targets.elements[0] ?? null;
        this.emitStateChange(key, element, undefined, undefined, wasInvalid !== this.invalidMessages.has(key));
    }

    clear(key: string): void {
        if (isNullOrUndefined(key)) {
            return;
        }
        this.trackedKeys.add(key);
        const changed = this.isModified(key) || this.isInvalid(key);
        this.modifiedStates.set(key, false);
        this.invalidMessages.delete(key);
        const targets = this.resolveTargets(key);
        this.applyKeyStateToSurfaces(key, targets.surfaces);
        const element = targets.elements[0] ?? null;
        this.emitStateChange(key, element, undefined, undefined, changed);
    }

    clearAll(): void {
        this.trackedKeys.forEach((key) => {
            const changed = this.isModified(key) || this.isInvalid(key);
            this.modifiedStates.set(key, false);
            this.invalidMessages.delete(key);
            const targets = this.resolveTargets(key);
            this.applyKeyStateToSurfaces(key, targets.surfaces);
            const element = targets.elements[0] ?? null;
            this.emitStateChange(key, element, undefined, undefined, changed);
        });
        this.trackedKeys.clear();
        this.modifiedStates.clear();
        this.invalidMessages.clear();
        this.keySurfaces.clear();
        this.surfaceStates = new WeakMap();
    }

    refresh(keys: string[] = []): void {
        const toRefresh = isArray(keys) && keys.length ? keys : Array.from(this.trackedKeys);
        toRefresh.forEach((key) => this.update(key));
    }

    reapplyDomState(): void {
        this.trackedKeys.forEach((key) => {
            this.applyKeyStateToSurfaces(key, this.resolveTargets(key).surfaces);
        });
    }

    isModified(key: string): boolean {
        return safeBoolean(this.modifiedStates.get(key));
    }

    isInvalid(key: string): boolean {
        return this.invalidMessages.has(key);
    }

    isValid(): boolean {
        return this.invalidMessages.size === 0;
    }

    hasPendingChanges(): boolean {
        return this.getModifiedKeys().length > 0 || !this.isValid();
    }

    getModifiedKeys(): string[] {
        return Array.from(this.trackedKeys).filter((key) => this.isModified(key));
    }

    private emitStateChange(key: string, element: Element | null, currentValue: JsonValue | null | undefined, originalValue: JsonValue | null | undefined, changed: boolean): void {
        if (!this.onStateChange || !changed) {
            return;
        }
        this.onStateChange({
            key,
            isModified: this.isModified(key),
            isInvalid: this.isInvalid(key),
            element,
            currentValue,
            originalValue
        });
    }

    private resolveElements(key: string): Element[] {
        if (this.getElements) {
            return this.getElements(key);
        }
        const element = this.getElement(key);
        return element ? [element] : [];
    }

    private resolveTargets(key: string): FieldTargets {
        const elements = this.resolveElements(key);
        const surfaces = new Set<Element>();
        for (const element of elements) {
            surfaces.add(requireFieldSurface(element));
        }
        return { elements, surfaces };
    }

    private getSurfaceState(surface: Element): FieldSurfaceState {
        const existing = this.surfaceStates.get(surface);
        if (existing) {
            return existing;
        }
        const created = { modifiedKeys: new Set<string>(), invalidKeys: new Set<string>() };
        this.surfaceStates.set(surface, created);
        return created;
    }

    private applyKeyStateToSurfaces(key: string, nextSurfaces: Set<Element>): void {
        const previousSurfaces = this.keySurfaces.get(key);
        const affectedSurfaces = new Set<Element>();
        if (previousSurfaces) {
            for (const surface of previousSurfaces) {
                affectedSurfaces.add(surface);
            }
        }
        for (const surface of nextSurfaces) {
            affectedSurfaces.add(surface);
        }
        this.keySurfaces.set(key, nextSurfaces);
        for (const surface of affectedSurfaces) {
            const state = this.getSurfaceState(surface);
            state.modifiedKeys.delete(key);
            state.invalidKeys.delete(key);
            if (nextSurfaces.has(surface)) {
                if (this.isModified(key)) {
                    state.modifiedKeys.add(key);
                }
                if (this.isInvalid(key)) {
                    state.invalidKeys.add(key);
                }
            }
            setFieldSurfaceModified(surface, state.modifiedKeys.size > 0);
            setFieldSurfaceInvalid(surface, state.invalidKeys.size > 0);
        }
    }
}

export { FieldStateTracker };
