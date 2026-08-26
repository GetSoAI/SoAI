/* SoAI - Shared primitives change notification source [frontend/assets/ts/core/primitives/changeNotificationSource.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ChangeNotificationListener = () => void;

class ChangeNotificationSource {
    readonly #listeners = new Set<ChangeNotificationListener>();

    subscribe(listener: ChangeNotificationListener): () => boolean {
        this.#listeners.add(listener);
        return () => this.#listeners.delete(listener);
    }

    notify(): void {
        for (const listener of this.#listeners) listener();
    }

    clear(): void {
        this.#listeners.clear();
    }
}

export { ChangeNotificationSource };
