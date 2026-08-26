/* SoAI - Generation-owned coalesced providers refresh controller [frontend/assets/ts/features/models/modals/providersmodal/ProvidersRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { ExternalProviderRecord } from '@core/api/contracts/pluginProviderContracts.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import type { ProviderRefreshFailure, ProvidersRefreshControllerDependencies, ProvidersRefreshResult } from '@features/models/modals/providersmodal/providersRefreshContracts.ts';

interface ActiveBatch {
    generation: number;
    promise: Promise<void>;
}

class ProvidersRefreshController {
    readonly #dependencies: ProvidersRefreshControllerDependencies;
    #generation = 0;
    #pluginRevision = 0;
    #dirtyRevision = 0;
    #plugins: readonly string[] = Object.freeze([]);
    #controller: AbortController | null = null;
    #activeBatch: ActiveBatch | null = null;
    #open = false;

    constructor(dependencies: ProvidersRefreshControllerDependencies) {
        if (!Number.isSafeInteger(dependencies.concurrency) || dependencies.concurrency < 1 || dependencies.concurrency > 16) throw new Error('Providers refresh concurrency is invalid');
        this.#dependencies = dependencies;
    }

    open(pluginNames: readonly string[]): void {
        this.#generation += 1;
        this.#controller?.abort();
        this.#controller = new AbortController();
        this.#plugins = this.#normalizePlugins(pluginNames);
        this.#pluginRevision += 1;
        this.#dirtyRevision += 1;
        this.#activeBatch = null;
        this.#open = true;
    }

    close(): void {
        this.#generation += 1;
        this.#open = false;
        this.#controller?.abort();
        this.#controller = null;
        this.#activeBatch = null;
    }

    updatePlugins(pluginNames: readonly string[]): void {
        const normalized = this.#normalizePlugins(pluginNames);
        if (arraysEqual(normalized, this.#plugins)) return;
        this.#plugins = normalized;
        this.#pluginRevision += 1;
        this.markDirty('plugin-set');
    }

    markDirty(_reason: string): void {
        if (!this.#open) return;
        this.#dirtyRevision += 1;
    }

    async refresh(_reason: string): Promise<void> {
        if (!this.#open) return;
        const generation = this.#generation;
        if (this.#activeBatch?.generation === generation) {
            await this.#activeBatch.promise;
            return;
        }
        const promise = this.#runLoop(generation).finally(() => {
            if (this.#activeBatch?.generation === generation && this.#activeBatch.promise === promise) this.#activeBatch = null;
        });
        this.#activeBatch = { generation, promise };
        await promise;
    }

    async #runLoop(generation: number): Promise<void> {
        let completedDirtyRevision = -1;
        while (this.#ownsGeneration(generation) && completedDirtyRevision !== this.#dirtyRevision) {
            const batchDirtyRevision = this.#dirtyRevision;
            const pluginRevision = this.#pluginRevision;
            const plugins = this.#plugins;
            const controller = this.#controller;
            if (!controller) return;
            const result = await this.#fetchBatch(plugins, pluginRevision, controller.signal);
            if (!this.#ownsGeneration(generation)) return;
            completedDirtyRevision = batchDirtyRevision;
            if (pluginRevision !== this.#pluginRevision || batchDirtyRevision !== this.#dirtyRevision) continue;
            this.#dependencies.publish(result);
            if (result.failures.length > 0) this.#dependencies.reportFailure(result.failures);
        }
    }

    async #fetchBatch(plugins: readonly string[], pluginRevision: number, signal: AbortSignal): Promise<ProvidersRefreshResult> {
        const providerGroups: Array<readonly ExternalProviderRecord[] | undefined> = [];
        const failureGroups: Array<ProviderRefreshFailure | undefined> = [];
        let cursor = 0;
        const worker = async (): Promise<void> => {
            while (cursor < plugins.length && !signal.aborted) {
                const pluginIndex = cursor;
                cursor += 1;
                const pluginName = plugins[pluginIndex];
                if (!pluginName) continue;
                try {
                    const records = await this.#dependencies.fetchPlugin(pluginName, signal);
                    providerGroups[pluginIndex] = records;
                } catch (error) {
                    if (signal.aborted) return;
                    failureGroups[pluginIndex] = Object.freeze({ pluginName, error: ensureError(error) });
                }
            }
        };
        const workerCount = Math.min(this.#dependencies.concurrency, Math.max(1, plugins.length));
        await Promise.all(Array.from({ length: workerCount }, worker));
        const providers = providerGroups.flatMap((records) => records ?? []);
        const successfulPlugins = plugins.filter((_pluginName, index) => providerGroups[index] !== undefined);
        const failures = failureGroups.filter((failure): failure is ProviderRefreshFailure => failure !== undefined);
        const status = failures.length === 0 ? 'ready' : successfulPlugins.length > 0 ? 'degraded' : 'unavailable';
        return Object.freeze({
            providers: Object.freeze(providers.slice()),
            requestedPlugins: plugins,
            successfulPlugins: Object.freeze(successfulPlugins.slice()),
            failures: Object.freeze(failures.slice()),
            sourcePluginRevision: pluginRevision,
            status
        });
    }

    #ownsGeneration(generation: number): boolean {
        return this.#open && generation === this.#generation;
    }

    #normalizePlugins(pluginNames: readonly string[]): readonly string[] {
        const unique = new Set<string>();
        for (const pluginName of pluginNames) {
            const normalized = pluginName.trim();
            if (!normalized) throw new Error('Provider plugin name must be non-empty');
            unique.add(normalized);
        }
        return Object.freeze([...unique].sort((left, right) => (left < right ? -1 : left > right ? 1 : 0)));
    }
}

export { ProvidersRefreshController };
