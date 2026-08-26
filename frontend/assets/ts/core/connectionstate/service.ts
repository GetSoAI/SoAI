/* SoAI - Shared connection state service [frontend/assets/ts/core/connectionstate/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler, type ErrorHandler } from '@core/errorHandler.ts';
import { getApiBaseUrl, normalizeApiBaseUrl } from '@core/runtimeconfiguration/public.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { captureConfiguredBaseUrl, notifyListeners, resolveWaiters, resolveStorageKey, updateBaseUrl } from '@core/connectionstate/actions.ts';
import { connectStorageSnapshotBridge } from '@core/connectionstate/effects.ts';
import { type BaseUrlListener, type ConnectionEndpoint, type ConnectionStateOptions, type OnChangeOptions, type UpdateOptions, type WhenReadyOptions } from '@core/connectionstate/contracts.ts';
import { subscribeBaseUrlChange, subscribeBaseUrlOnce } from '@core/connectionstate/listeners.ts';
import { createConnectionStateState, type ConnectionStateState } from '@core/connectionstate/state.ts';
import { whenBaseUrlReady } from '@core/connectionstate/waiters.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { isKeyValueStorageContract } from '@core/storage/guards.ts';

class ConnectionState {
    #state: ConnectionStateState;

    constructor(options: ConnectionStateOptions) {
        if (!isObject(options)) {
            throw new Error('ConnectionState options must be an object');
        }

        if (!isKeyValueStorageContract(options.storage)) {
            throw new Error('ConnectionState requires a storage service with get/set');
        }

        const configuredErrorHandler: ErrorHandler | undefined = options.errorHandler ?? errorHandler;

        let runtimeConfiguredBaseUrl: string | null = null;
        try {
            runtimeConfiguredBaseUrl = this.normalizeBaseUrl(getApiBaseUrl());
        } catch (error) {
            runtimeConfiguredBaseUrl = null;
            const runtimeError = ensureError(error);
            configuredErrorHandler?.warn?.('ConnectionState', 'Runtime API base URL normalization failed', runtimeError);
        }

        const storageKey = resolveStorageKey();
        this.#state = createConnectionStateState({
            errorHandler: configuredErrorHandler,
            storage: options.storage,
            storageKey,
            runtimeConfiguredBaseUrl
        });
    }

    private normalizeBaseUrl(value: string | null): string | null {
        if (value === null) {
            return null;
        }
        return normalizeApiBaseUrl(value);
    }

    initialize(): Promise<void> {
        if (this.#state.initializePromise) {
            return this.#state.initializePromise;
        }

        this.#state.initializePromise = (async () => {
            const initialBaseUrl = this.#captureConfiguredBaseUrl();
            if (initialBaseUrl) {
                this.#updateBaseUrl(initialBaseUrl, {
                    silent: false,
                    instanceId: this.#state.instanceId
                });
            }

            try {
                await this.#connectStorageSnapshotBridge();
            } catch (error) {
                const runtimeError = ensureError(error);
                this.#warn('Storage snapshot bridge connection failed', runtimeError);
            }
        })();

        return this.#state.initializePromise;
    }

    getBaseUrl(): string | null {
        return this.#state.baseUrl;
    }

    hasBaseUrl(): boolean {
        return isString(this.#state.baseUrl) && this.#state.baseUrl.length > 0;
    }

    getInstanceId(): string | null {
        return this.#state.instanceId;
    }

    setEndpoint(endpoint: ConnectionEndpoint): string | null {
        const normalized = this.normalizeBaseUrl(endpoint.baseUrl);
        if (!normalized || !endpoint.instanceId.trim()) {
            throw new Error('ConnectionState requires a valid endpoint and instance identity');
        }
        return this.#updateBaseUrl(normalized, {
            instanceId: endpoint.instanceId.trim()
        });
    }

    setBaseUrl(value: string, options: { silent?: boolean; releaseConfigured?: boolean } = {}): string | null {
        const normalized = this.normalizeBaseUrl(value);
        if (!normalized) {
            throw new Error('ConnectionState requires a valid base URL');
        }
        return this.#updateBaseUrl(normalized, options);
    }

    clearBaseUrl(options: { silent?: boolean; releaseConfigured?: boolean } = {}): string | null {
        return this.#updateBaseUrl(null, options);
    }

    getConfiguredBaseUrl(): string | null {
        if (!this.#state.allowConfiguredFallback) {
            return null;
        }
        if (this.#state.persistedBaseUrl) {
            return this.#state.persistedBaseUrl;
        }
        return this.#state.runtimeConfiguredBaseUrl;
    }

    onChange(listener: BaseUrlListener, options: OnChangeOptions = {}): () => void {
        const safeOptions = isObject(options) ? options : {};
        return subscribeBaseUrlChange(this.#state, listener, safeOptions, (message: string, error: Error) => this.#warn(message, error));
    }

    once(listener: BaseUrlListener, options: OnChangeOptions = {}): () => void {
        const safeOptions = isObject(options) ? options : {};
        return subscribeBaseUrlOnce(this.#state, listener, safeOptions, (message: string, error: Error) => this.#warn(message, error));
    }

    whenReady(options: WhenReadyOptions = {}): Promise<string> {
        return whenBaseUrlReady(this.#state, options);
    }

    #updateBaseUrl(value: string | null, options: UpdateOptions = {}): string | null {
        const warn = (message: string, error: Error): void => {
            this.#warn(message, error);
        };

        return updateBaseUrl(this.#state, value, options, {
            notifyListeners: (listenerValue: string | null): void => {
                notifyListeners(this.#state.listeners, listenerValue, warn);
            },
            resolveWaiters: (waiterValue: string | null): void => {
                resolveWaiters(this.#state.waiters, waiterValue, warn);
            }
        });
    }

    #captureConfiguredBaseUrl(): string | null {
        return captureConfiguredBaseUrl(this.#state, {
            normalizeBaseUrl: (value: string): string | null => {
                return this.normalizeBaseUrl(value);
            }
        });
    }

    #connectStorageSnapshotBridge(): Promise<void> {
        const warn = (message: string, error: Error): void => {
            this.#warn(message, error);
        };

        return connectStorageSnapshotBridge(this.#state, {
            notifyListeners: (value: string | null): void => {
                notifyListeners(this.#state.listeners, value, warn);
            },
            resolveWaiters: (value: string | null): void => {
                resolveWaiters(this.#state.waiters, value, warn);
            },
            updateBaseUrl: (value: string | null, options: { silent?: boolean; releaseConfigured?: boolean }): string | null => {
                return this.#updateBaseUrl(value, options);
            },
            normalizeBaseUrl: (value: string): string | null => {
                return this.normalizeBaseUrl(value);
            },
            onWarn: (message: string, error: Error): void => {
                warn(message, error);
            }
        });
    }

    #warn(message: string, error: Error): void {
        this.#state.errorHandler?.warn?.('ConnectionState', message, error);
    }
}

const createConnectionState = (options: ConnectionStateOptions): ConnectionState => new ConnectionState(options);

const CONNECTION_STATE_SERVICE_ID = 'core.connectionState';

const getConnectionState = (): ConnectionState => {
    const candidate = resolveKernelService(CONNECTION_STATE_SERVICE_ID);
    if (!(candidate instanceof ConnectionState)) {
        throw new Error(`${CONNECTION_STATE_SERVICE_ID} is not registered`);
    }
    return candidate;
};

export { ConnectionState, CONNECTION_STATE_SERVICE_ID, createConnectionState, getConnectionState };
export type { ConnectionEndpoint, ConnectionStateOptions, BaseUrlListener, OnChangeOptions, WhenReadyOptions };
