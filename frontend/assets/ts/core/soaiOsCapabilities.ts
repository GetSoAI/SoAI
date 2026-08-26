/* SoAI - Shared frontend SoAI OS capabilities [frontend/assets/ts/core/soaiOsCapabilities.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { getDiscoveryService } from '@core/discoveryservice/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError, requireErrorMessage } from '@core/errors/coerce.ts';
import type { SoaiOsCapabilitiesService, SoaiOsCapabilitiesSnapshot } from '@core/soaiOsAccess.ts';
import { hasOwn } from '@core/typeGuards.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import type { OsCapabilitiesResponse } from '@core/api/contracts/osSystemContracts.ts';
import type { SystemHealthResponse } from '@core/api/contracts/systemContracts.ts';

type SoaiOsCapabilitiesListener = (snapshot: SoaiOsCapabilitiesSnapshot) => void;

interface ApiClientContract {
    whenReady: (options?: { allowDiscovery?: boolean; signal?: AbortSignal }) => Promise<string>;
    system: { health: () => Promise<SystemHealthResponse> };
    os: { capabilities: () => Promise<OsCapabilitiesResponse> } | null;
}

interface AuthContract {
    isAuthenticated: boolean;
}

interface SoaiOsCapabilitiesDependencies {
    api: ApiClientContract;
    auth: AuthContract;
}

interface EnsureReadyOptions {
    timeoutMs?: number;
}

class SoaiOsCapabilities implements SoaiOsCapabilitiesService {
    #dependencies: SoaiOsCapabilitiesDependencies;
    #listeners: Set<SoaiOsCapabilitiesListener>;
    #initializePromise: Promise<void> | null;
    #snapshot: SoaiOsCapabilitiesSnapshot;

    constructor(dependencies: SoaiOsCapabilitiesDependencies) {
        this.#dependencies = dependencies;
        this.#listeners = new Set();
        this.#initializePromise = null;
        this.#snapshot = {
            initialized: false,
            osModeEnabled: false,
            osAccessible: false,
            accessState: 'unknown',
            capabilities: null,
            lastError: null
        };
    }

    initialize(): Promise<void> {
        if (!this.#initializePromise) {
            this.#initializePromise = (async (): Promise<void> => {
                this.#applySnapshot({ initialized: true });
            })();
        }
        return this.#initializePromise;
    }

    async ensureReady(options: EnsureReadyOptions = {}): Promise<void> {
        const initializeTask = this.initialize();
        const timeoutMs = Number(options.timeoutMs);
        if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
            await initializeTask;
            return;
        }
        await withTimeout(initializeTask, { timeoutMs: timeoutMs, timeoutMessage: `core.soaiOsCapabilities.initialize timed out after ${timeoutMs}ms` });
    }

    isSoaiOsEnabled(): boolean {
        return this.#snapshot.osModeEnabled;
    }

    isSoaiOsAccessible(): boolean {
        return this.#snapshot.osAccessible;
    }

    getOsCapabilities(): SoaiOsCapabilitiesSnapshot['capabilities'] {
        const capabilities = this.#snapshot.capabilities;
        if (!capabilities) {
            return null;
        }
        return { ...capabilities };
    }

    getSnapshot(): SoaiOsCapabilitiesSnapshot {
        return {
            initialized: this.#snapshot.initialized,
            osModeEnabled: this.#snapshot.osModeEnabled,
            osAccessible: this.#snapshot.osAccessible,
            accessState: this.#snapshot.accessState,
            capabilities: this.#snapshot.capabilities ? { ...this.#snapshot.capabilities } : null,
            lastError: this.#snapshot.lastError
        };
    }

    onChange(listener: SoaiOsCapabilitiesListener, options: { immediate?: boolean } = {}): () => void {
        this.#listeners.add(listener);
        if (options.immediate !== false) {
            try {
                listener(this.getSnapshot());
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('SoaiOsCapabilities', 'Snapshot listener failed during immediate dispatch', runtimeError);
            }
        }
        return () => {
            this.#listeners.delete(listener);
        };
    }

    async refreshAccess(): Promise<void> {
        await this.ensureReady();
        await this.#probeAccess();
    }

    clearAccess(): void {
        this.#applySnapshot({
            osAccessible: false,
            accessState: this.#snapshot.osModeEnabled ? 'unknown' : 'unavailable',
            capabilities: null,
            lastError: null
        });
    }

    async #probeAccess(): Promise<void> {
        const osApi = this.#dependencies.api.os;
        if (osApi === null) {
            this.#applySnapshot({
                osModeEnabled: false,
                osAccessible: false,
                accessState: 'unavailable',
                capabilities: null,
                lastError: null
            });
            return;
        }
        try {
            await this.#dependencies.api.whenReady({ allowDiscovery: true });
            const discoveredEdition = await this.#resolveKnownEdition();
            if (discoveredEdition !== 'soai-os') {
                this.#applySnapshot({
                    osModeEnabled: false,
                    osAccessible: false,
                    accessState: 'unavailable',
                    capabilities: null,
                    lastError: null
                });
                return;
            }
            const payload = await osApi.capabilities();
            const capabilities = payload.capabilities;
            const osModeEnabled = payload.enabled;
            this.#applySnapshot({
                osModeEnabled,
                osAccessible: osModeEnabled,
                accessState: osModeEnabled ? 'granted' : 'unavailable',
                capabilities,
                lastError: null
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#applySnapshot(this.#normalizeAccessError(runtimeError));
        }
    }

    async #resolveKnownEdition(): Promise<'soai-core' | 'soai-os'> {
        const discoveryService = getDiscoveryService();
        const discoveredEdition = discoveryService.getEdition();
        if (discoveredEdition !== null) {
            return discoveredEdition;
        }
        const healthPayload = await this.#dependencies.api.system.health();
        return healthPayload.edition;
    }

    #normalizeAccessError(error: Error): Partial<SoaiOsCapabilitiesSnapshot> {
        if (error instanceof APIError) {
            if (error.status === 401) {
                return {
                    osModeEnabled: true,
                    osAccessible: false,
                    accessState: this.#dependencies.auth.isAuthenticated ? 'denied' : 'unknown',
                    capabilities: null,
                    lastError: requireErrorMessage(error, 'Unknown error')
                };
            }
            if (error.status === 403) {
                return {
                    osModeEnabled: true,
                    osAccessible: false,
                    accessState: 'denied',
                    capabilities: null,
                    lastError: requireErrorMessage(error, 'Unknown error')
                };
            }
            if (error.status === 404 || error.status === 412) {
                return {
                    osModeEnabled: false,
                    osAccessible: false,
                    accessState: 'unavailable',
                    capabilities: null,
                    lastError: requireErrorMessage(error, 'Unknown error')
                };
            }
        }

        return {
            osAccessible: false,
            accessState: 'unknown',
            capabilities: null,
            lastError: requireErrorMessage(error, 'Unknown error')
        };
    }

    #applySnapshot(next: Partial<SoaiOsCapabilitiesSnapshot>): void {
        const hasCapabilities = hasOwn(next, 'capabilities');
        const hasLastError = hasOwn(next, 'lastError');
        const merged: SoaiOsCapabilitiesSnapshot = {
            initialized: typeof next.initialized === 'boolean' ? next.initialized : this.#snapshot.initialized,
            osModeEnabled: typeof next.osModeEnabled === 'boolean' ? next.osModeEnabled : this.#snapshot.osModeEnabled,
            osAccessible: typeof next.osAccessible === 'boolean' ? next.osAccessible : this.#snapshot.osAccessible,
            accessState: next.accessState ?? this.#snapshot.accessState,
            capabilities: hasCapabilities ? (next.capabilities ?? null) : this.#snapshot.capabilities,
            lastError: hasLastError ? (next.lastError ?? null) : this.#snapshot.lastError
        };

        const changed = merged.initialized !== this.#snapshot.initialized || merged.osModeEnabled !== this.#snapshot.osModeEnabled || merged.osAccessible !== this.#snapshot.osAccessible || merged.accessState !== this.#snapshot.accessState || merged.capabilities !== this.#snapshot.capabilities || merged.lastError !== this.#snapshot.lastError;
        if (!changed) {
            return;
        }

        this.#snapshot = merged;
        this.#listeners.forEach((listener) => {
            try {
                listener(this.getSnapshot());
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('SoaiOsCapabilities', 'Snapshot listener failed', runtimeError);
            }
        });
    }
}

const createSoaiOsCapabilities = (dependencies: SoaiOsCapabilitiesDependencies): SoaiOsCapabilities => new SoaiOsCapabilities(dependencies);

export { createSoaiOsCapabilities };
export type { ApiClientContract, AuthContract, EnsureReadyOptions, SoaiOsCapabilitiesDependencies, SoaiOsCapabilitiesSnapshot };
