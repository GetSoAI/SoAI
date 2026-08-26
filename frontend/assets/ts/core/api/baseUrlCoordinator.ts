/* SoAI - Shared API base URL coordinator [frontend/assets/ts/core/api/baseUrlCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { probeApiBaseUrl, probeCurrentOriginApiEndpoint } from '@core/api/probeCurrentOriginApiBaseUrl.ts';
import { resolveDefaultApiBaseUrl } from '@core/api/actions.ts';
import { assertNonNull } from '@core/assertions.ts';
import { getConnectionState, type ConnectionState } from '@core/connectionstate/service.ts';
import { dispatchCustomEvent, getLocation } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { coerceErrorMessage } from '@core/errors/coerce.ts';
import { isFunction, isNullOrUndefined } from '@core/typeGuards.ts';
import { resolveDiscoveryService } from '@core/api/guards.ts';
import { normalizeRuntimeErrorValue } from '@core/api/mappers.ts';
import { raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import type { ConnectionEndpoint } from '@core/connectionstate/connectionEndpoint.ts';
import { isBackendEditionIntegrityError } from '@core/edition/backendEditionIntegrity.ts';

class ApiBaseUrlCoordinator {
    #connectionStateRef: ConnectionState | null = null;
    #connectionStateUnsubscribe: (() => void) | null = null;
    #lastKnownBaseUrl: string | null = null;
    discoveryPromise: Promise<string> | null = null;
    discoveryComplete = false;
    initialized = false;

    get connectionState(): ConnectionState {
        if (this.#connectionStateRef) {
            return this.#connectionStateRef;
        }
        const resolved = getConnectionState();
        this.#connectionStateRef = resolved;
        this.#lastKnownBaseUrl = resolved.getBaseUrl() || null;
        this.#connectionStateUnsubscribe = resolved.onChange((base) => this.#applyBaseUrlChange(base), { immediate: true });
        return resolved;
    }

    async ensureBaseUrl(options: { allowDiscovery?: boolean; signal?: AbortSignal } = {}): Promise<string> {
        const { allowDiscovery = true, signal } = options;
        throwIfAborted(signal);
        const existing = this.connectionState.getBaseUrl();
        if (existing) {
            this.discoveryComplete = true;
            return existing;
        }
        const originEndpoint = await probeCurrentOriginApiEndpoint(signal ? { signal } : {});
        throwIfAborted(signal);
        if (originEndpoint) {
            this.connectionState.setEndpoint(originEndpoint);
            const baseUrl = this.getBaseUrl();
            assertNonNull(baseUrl, 'API base URL');
            return baseUrl;
        }
        const fallback = resolveDefaultApiBaseUrl(this.connectionState);
        if (fallback) {
            this.setBaseUrl(fallback);
            const baseUrl = this.getBaseUrl();
            assertNonNull(baseUrl, 'API base URL');
            return baseUrl;
        }
        if (!allowDiscovery) {
            throw new Error('API base URL is not configured and discovery is disabled');
        }
        if (!this.discoveryPromise) {
            this.discoveryPromise = this.discoverAndSetBaseUrl().finally(() => {
                this.discoveryPromise = null;
            });
        }
        return signal ? raceWithAbortSignal(this.discoveryPromise, signal) : this.discoveryPromise;
    }

    async whenReady(options: { allowDiscovery?: boolean; signal?: AbortSignal } = {}): Promise<string> {
        const existing = this.connectionState.getBaseUrl();
        if (existing) {
            return existing;
        }
        const allowDiscovery = options.allowDiscovery !== false;
        const readyOptions: { allowDiscovery: boolean; signal?: AbortSignal } = { allowDiscovery };
        if (options.signal) {
            readyOptions.signal = options.signal;
        }
        return this.ensureBaseUrl(readyOptions);
    }

    async revalidateBaseUrl(baseUrl: string): Promise<boolean> {
        try {
            const resolved = await probeApiBaseUrl(baseUrl);
            return resolved !== null;
        } catch (error) {
            const runtimeError = normalizeRuntimeErrorValue(error);
            errorHandler.debug('ApiClient', `Base URL revalidation failed: ${coerceErrorMessage(runtimeError)}`, runtimeError);
            return false;
        }
    }

    async recoverBaseUrl(options: { allowDiscovery?: boolean; shouldContinue: () => boolean }): Promise<string | null> {
        const { allowDiscovery = true, shouldContinue } = options;
        if (!shouldContinue()) {
            return null;
        }
        const existing = this.connectionState.getBaseUrl();
        if (existing) {
            return existing;
        }
        let originEndpoint: ConnectionEndpoint | null = null;
        try {
            originEndpoint = await probeCurrentOriginApiEndpoint();
        } catch (error) {
            const runtimeError = normalizeRuntimeErrorValue(error);
            errorHandler.debug('ApiClient', `Recovery current-origin probe failed: ${coerceErrorMessage(runtimeError)}`, runtimeError);
        }
        if (!shouldContinue()) {
            return null;
        }
        const current = this.connectionState.getBaseUrl();
        if (current) {
            return current;
        }
        if (originEndpoint) {
            this.connectionState.setEndpoint(originEndpoint);
            return this.getBaseUrl();
        }
        const fallback = resolveDefaultApiBaseUrl(this.connectionState);
        if (!shouldContinue()) {
            return null;
        }
        if (fallback) {
            this.setBaseUrl(fallback);
            return this.getBaseUrl();
        }
        if (!allowDiscovery) {
            throw new Error('API base URL is not configured and discovery is disabled');
        }
        const discovered = await this.#resolveDiscoveredEndpoint();
        if (!shouldContinue()) {
            return null;
        }
        const latest = this.connectionState.getBaseUrl();
        if (latest) {
            return latest;
        }
        this.connectionState.setEndpoint(discovered);
        return this.getBaseUrl();
    }

    onReady(listener: (baseUrl: string | null) => void, options: { immediate?: boolean; ensure?: boolean; allowDiscovery?: boolean } = {}): () => void {
        if (this.connectionState.hasBaseUrl() && options.immediate !== false) {
            listener(this.connectionState.getBaseUrl());
            return () => {};
        }
        const unsubscribe = this.connectionState.once((base) => listener(base), { immediate: false });
        if (options.ensure !== false) {
            void this.whenReady(options).catch((error) => {
                errorHandler.warn('ApiClient', 'Background ready check failed', error);
            });
        }
        return unsubscribe;
    }

    async discoverAndSetBaseUrl(): Promise<string> {
        const current = this.connectionState.getBaseUrl();
        if (current && this.discoveryComplete) {
            return current;
        }
        const resolved = await this.#resolveDiscoveredEndpoint();
        this.connectionState.setEndpoint(resolved);
        const baseUrl = this.getBaseUrl();
        assertNonNull(baseUrl, 'Discovered API base URL');
        return baseUrl;
    }

    async #resolveDiscoveredEndpoint(): Promise<ConnectionEndpoint> {
        const discoveryServiceRef = await resolveDiscoveryService();
        try {
            if (isFunction(discoveryServiceRef.reset)) {
                discoveryServiceRef.reset();
            }
            const loc: Location = getLocation();
            return await discoveryServiceRef.discoverEndpoint(loc.hostname, this.connectionState.getInstanceId());
        } catch (error) {
            this.discoveryComplete = false;
            this.initialized = false;
            const discoveryError = normalizeRuntimeErrorValue(error);
            if (isBackendEditionIntegrityError(discoveryError)) throw discoveryError;
            throw new Error(`Port discovery failed: ${coerceErrorMessage(discoveryError)}`);
        }
    }

    setBaseUrl(baseUrl: string | null | undefined): void {
        if (isNullOrUndefined(baseUrl) || baseUrl === '') {
            this.clearBaseUrl();
            return;
        }
        this.connectionState.setBaseUrl(baseUrl);
    }

    clearBaseUrl(): void {
        this.connectionState.clearBaseUrl();
    }

    onBaseUrlChange(listener: (baseUrl: string | null) => void): () => void {
        if (this.hasBaseUrl()) {
            listener(this.getBaseUrl());
        }
        return this.connectionState.onChange((value) => listener(value), { immediate: false });
    }

    getBaseUrl(): string | null {
        return this.connectionState.getBaseUrl() || null;
    }

    hasBaseUrl(): boolean {
        return this.connectionState.hasBaseUrl();
    }

    reset(): void {
        if (this.#connectionStateUnsubscribe) {
            this.#connectionStateUnsubscribe();
            this.#connectionStateUnsubscribe = null;
        }
        this.#connectionStateRef = null;
        this.#lastKnownBaseUrl = null;
        this.discoveryPromise = null;
        this.discoveryComplete = false;
        this.initialized = false;
    }

    #applyBaseUrlChange(baseUrl: string | null): void {
        const normalized = baseUrl || null;
        const previous = this.#lastKnownBaseUrl;
        this.#lastKnownBaseUrl = normalized;
        this.discoveryComplete = Boolean(normalized);
        this.initialized = Boolean(normalized);
        if (previous === normalized) {
            return;
        }
        dispatchCustomEvent('soai:api:base-url', { baseUrl: normalized });
    }
}

export { ApiBaseUrlCoordinator };
