/* SoAI - Shared settings section lifecycle [frontend/assets/ts/features/settings/sectionLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleScope, type LifecycleRun } from '@core/lifecycle/lifecycleScope.ts';

const runSettingsSectionCleanups = (cleanups: readonly (() => void)[], message: string): void => {
    const cleanupErrors: Error[] = [];
    for (const cleanup of cleanups) {
        try {
            cleanup();
        } catch (error) {
            cleanupErrors.push(ensureError(error));
        }
    }
    if (cleanupErrors.length === 1) {
        throw cleanupErrors[0];
    }
    if (cleanupErrors.length > 1) {
        throw new AggregateError(cleanupErrors, message);
    }
};

class SettingsSectionLifecycle {
    readonly #reloadScope: LifecycleScope = new LifecycleScope();
    #cleanups: Array<() => void> = [];
    #cleanupGroups: Map<string, Array<() => void>> = new Map();
    #isMounted = false;

    mount(): void {
        this.dispose('settings-section-remount');
        this.#isMounted = true;
    }

    addCleanup(cleanup: () => void): void {
        if (!this.#isMounted) {
            cleanup();
            return;
        }
        this.#cleanups.push(cleanup);
    }

    replaceCleanupGroup(groupId: string, createCleanups: () => readonly (() => void)[], message: string): void {
        this.clearCleanupGroup(groupId, message);
        const cleanups = createCleanups();
        if (!this.#isMounted) {
            runSettingsSectionCleanups(cleanups, message);
            return;
        }
        this.#cleanupGroups.set(groupId, [...cleanups]);
    }

    clearCleanupGroup(groupId: string, message: string): void {
        const cleanups = this.#cleanupGroups.get(groupId);
        if (cleanups === undefined) {
            return;
        }
        this.#cleanupGroups.delete(groupId);
        runSettingsSectionCleanups(cleanups, message);
    }

    createAbortSignal(reason: string): AbortSignal {
        const controller = new AbortController();
        this.addCleanup(() => controller.abort(reason));
        return controller.signal;
    }

    dispose(reason: string): void {
        const cleanups = this.#collectAllCleanups();
        this.#cleanups = [];
        this.#cleanupGroups.clear();
        this.#isMounted = false;
        this.#reloadScope.abort(reason);
        runSettingsSectionCleanups(cleanups, `${reason} failed while running settings section cleanups`);
    }

    beginReload(reason: string): LifecycleRun | null {
        if (!this.#isMounted) {
            return null;
        }
        return this.#reloadScope.begin(reason);
    }

    isReloadCurrent(run: LifecycleRun): boolean {
        return this.#isMounted && this.#reloadScope.isCurrent(run);
    }

    get isMounted(): boolean {
        return this.#isMounted;
    }

    #collectAllCleanups(): Array<() => void> {
        const cleanups: Array<() => void> = [];
        for (const groupCleanups of this.#cleanupGroups.values()) {
            cleanups.push(...groupCleanups);
        }
        cleanups.push(...this.#cleanups);
        return cleanups;
    }
}

export { SettingsSectionLifecycle };
