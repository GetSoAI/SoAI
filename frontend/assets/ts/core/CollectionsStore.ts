/* SoAI - Shared frontend collections store [frontend/assets/ts/core/CollectionsStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue } from '@core/data/clientdatahub/types.ts';
import { isArray, isNullOrUndefined, isNumber, isObject } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

const DEFAULT_ID_KEY = 'id';

type StoreFieldValue = ResourceIncomingValue | symbol;
type StoreItemRecord = Record<string, StoreFieldValue>;
type IdNormalizer<T extends StoreItemRecord = StoreItemRecord> = (item: T) => StoreFieldValue;
type FilterFunction<T> = (item: T) => boolean;
type SortFunction<T> = (firstValue: T, secondValue: T) => number;
type UpdateFunction<T> = (item: T) => T | null;

interface CollectionsStoreOptions<T extends StoreItemRecord> {
    idKey?: string;
    normalizeId?: IdNormalizer<T> | null;
    items?: T[];
}

interface ApplyOptions<T> {
    filter?: FilterFunction<T> | null;
    sort?: SortFunction<T> | null;
}

class CollectionsStore<T extends StoreItemRecord = StoreItemRecord> {
    #normalizationGuards: WeakSet<WeakKey> | null = null;
    idKey: string;
    normalizeId: IdNormalizer<T> | null;
    items: Map<string, T>;
    order: string[];
    index: Map<string, number>;
    filtered: T[];
    filterFunctionValue: FilterFunction<T> | null;
    sortFunctionValue: SortFunction<T> | null;

    constructor(options: CollectionsStoreOptions<T> = {}) {
        const { idKey = DEFAULT_ID_KEY, normalizeId = null, items = [] } = options;
        this.idKey = idKey;
        this.normalizeId = typeof normalizeId === 'function' ? normalizeId : null;
        this.items = new Map();
        this.order = [];
        this.index = new Map();
        this.filtered = [];
        this.filterFunctionValue = null;
        this.sortFunctionValue = null;
        this.#normalizationGuards = typeof WeakSet === 'function' ? new WeakSet() : null;
        if (isArray(items) && items.length > 0) {
            this.#replace(items);
        }
    }

    replace(list: T[] = []): T[] {
        return this.#replace(list);
    }

    #replace(list: T[]): T[] {
        this.items.clear();
        this.order = [];
        this.index.clear();
        this.filtered = [];
        list.forEach((item) => {
            const id = this.#resolveId(item);
            if (!isNullOrUndefined(id)) {
                this.items.set(id, item);
                this.order.push(id);
            }
        });
        this.#reindex();
        this.#rebuildFiltered();
        return this.filtered.slice();
    }

    upsert(item: T): T | null {
        const id = this.#resolveId(item);
        if (isNullOrUndefined(id)) return null;
        let result = item;
        if (this.items.has(id)) {
            const existing = this.items.get(id);
            result = { ...existing, ...item };
            this.items.set(id, result);
        } else {
            this.items.set(id, item);
            this.order.push(id);
            this.index.set(id, this.order.length - 1);
        }
        this.#rebuildFiltered();
        return result;
    }

    update(idOrItem: string | T, updates: Partial<T> | UpdateFunction<T>): T | null {
        const id = this.#normalizeIdInput(idOrItem);
        if (id === null) return null;
        const current = this.items.get(id);
        if (!current) return null;
        let next: T | null;
        if (typeof updates === 'function') {
            next = updates({ ...current });
            if (next === null) {
                return current;
            }
        } else {
            next = { ...current, ...updates };
        }
        if (!isObject(next)) {
            throw new Error('CollectionsStore.update must return an object');
        }
        this.items.set(id, next);
        this.#rebuildFiltered();
        return next;
    }

    remove(idOrItem: string | T): boolean {
        const id = this.#normalizeIdInput(idOrItem);
        if (id === null) return false;
        if (!this.items.has(id)) return false;
        this.items.delete(id);
        const index = this.index.get(id);
        if (isNumber(index) && index < this.order.length && this.order[index] === id) {
            this.order.splice(index, 1);
        } else {
            this.order = this.order.filter((index) => index !== id);
        }
        this.#reindex();
        this.#rebuildFiltered();
        return true;
    }

    clear(): void {
        this.items.clear();
        this.order = [];
        this.index.clear();
        this.filtered = [];
    }

    apply({ filter, sort }: ApplyOptions<T> = {}): T[] {
        if (filter !== undefined) this.filterFunctionValue = typeof filter === 'function' ? filter : null;
        if (sort !== undefined) this.sortFunctionValue = typeof sort === 'function' ? sort : null;
        return this.#rebuildFiltered();
    }

    refresh(): T[] {
        return this.#rebuildFiltered();
    }

    #getOrderedItems(): T[] {
        return this.order.reduce<T[]>((acc, id) => {
            const item = this.items.get(id);
            if (item) acc.push(item);
            return acc;
        }, []);
    }

    getAll(): T[] {
        return this.#getOrderedItems();
    }

    getFiltered(): T[] {
        return this.filtered.slice();
    }

    find(idOrItem: string | T): T | null {
        const id = this.#normalizeIdInput(idOrItem);
        if (id === null) return null;
        return this.items.get(id) || null;
    }

    size(): number {
        return this.order.length;
    }

    isEmpty(): boolean {
        return this.order.length === 0;
    }

    #resolveId(candidate: T | null | undefined): string | null {
        if (!candidate || !isObject(candidate)) return null;
        const object = candidate;
        if (this.normalizeId) {
            const guard = this.#normalizationGuards;
            const hasGuard = guard && typeof guard.has === 'function';
            if (hasGuard) {
                if (guard.has(object)) {
                    return null;
                }
                guard.add(object);
            }
            try {
                const value = this.normalizeId(object);
                return isNullOrUndefined(value) ? null : String(value);
            } catch (error) {
                throw ensureError(error);
            } finally {
                if (hasGuard) {
                    guard.delete(object);
                }
            }
        }
        const key = object[this.idKey];
        return isNullOrUndefined(key) ? null : String(key);
    }

    #normalizeIdInput(value: string | T): string | null {
        if (value && isObject(value)) return this.#resolveId(value);
        return value ? String(value) : null;
    }

    #reindex(): void {
        this.index.clear();
        this.order.forEach((id, position) => this.index.set(id, position));
    }

    #rebuildFiltered(): T[] {
        let result = this.#getOrderedItems();
        if (this.filterFunctionValue) result = result.filter(this.filterFunctionValue);
        if (this.sortFunctionValue) result.sort(this.sortFunctionValue);
        this.filtered = result;
        return this.getFiltered();
    }
}

export { CollectionsStore };
export type { CollectionsStoreOptions, ApplyOptions, IdNormalizer, FilterFunction, SortFunction, StoreFieldValue, StoreItemRecord, UpdateFunction };
