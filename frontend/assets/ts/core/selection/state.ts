/* SoAI - Shared selection state for multi-select UIs [frontend/assets/ts/core/selection/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class SelectionState {
    #active = false;
    readonly #selected = new Set<string>();

    isActive(): boolean {
        return this.#active;
    }

    setActive(active: boolean): void {
        this.#active = active;
    }

    has(key: string): boolean {
        return this.#selected.has(key);
    }

    keys(): ReadonlySet<string> {
        return new Set(this.#selected);
    }

    list(): readonly string[] {
        return Array.from(this.#selected);
    }

    size(): number {
        return this.#selected.size;
    }

    clear(): void {
        this.#selected.clear();
    }

    toggle(key: string): void {
        if (this.#selected.has(key)) {
            this.#selected.delete(key);
            return;
        }
        this.#selected.add(key);
    }

    removeMany(keys: readonly string[]): void {
        for (const key of keys) {
            this.#selected.delete(key);
        }
    }

    addMany(keys: readonly string[]): void {
        for (const key of keys) {
            this.#selected.add(key);
        }
    }
}

export { SelectionState };
