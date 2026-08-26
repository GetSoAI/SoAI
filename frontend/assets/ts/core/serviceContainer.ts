/* SoAI - Shared frontend service container [frontend/assets/ts/core/serviceContainer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import { hasFunctionProperty, isObject, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface ServiceMetadata {
    registeredAt: number;
    initialized: boolean;
    initializedAt?: number | undefined;
    moduleId?: string | undefined;
}

interface WaiterEntry {
    resolve: (value: SoAIRegisteredService) => void;
    reject: (error: Error) => void;
    timer: ReturnType<typeof setTimeout> | null;
}

interface WaitForOptions {
    timeoutMs?: number;
}

interface ServiceInfo {
    name: string;
    instance: SoAIRegisteredService;
    metadata: ServiceMetadata | undefined;
}

interface InitializeResult {
    name: string;
    initialized?: boolean;
    skipped?: boolean;
    error?: Error | null;
}

interface InitializableService {
    initialize: (options?: { force?: boolean | undefined }) => Promise<void | boolean | null> | void | boolean | null;
}

const isCanonicalServiceId = (value: string): boolean => value.startsWith('core.') || value.startsWith('features.') || value.startsWith('pages.');

const isInitializableService = (value: SoAIRegisteredService | null | undefined): value is SoAIRegisteredService & InitializableService => isObject(value) && hasFunctionProperty(value, 'initialize');

const normalizeServiceName = (name: string): string => {
    const normalized = assertNonEmptyString(name, 'Service name');
    if (!isCanonicalServiceId(normalized)) {
        throw new Error(`Service id must be canonical (core.*, features.*, pages.*). Got '${normalized}'`);
    }
    return normalized;
};

class ServiceContainer {
    readonly #services = new Map<string, SoAIRegisteredService>();
    readonly #pendingInitializations = new Map<string, Promise<SoAIRegisteredService | null>>();
    readonly #serviceMetadata = new Map<string, ServiceMetadata>();
    readonly #serviceWaiters = new Map<string, Set<WaiterEntry>>();

    #resolveWaiters(name: string, value: SoAIRegisteredService): void {
        const waiters = this.#serviceWaiters.get(name);
        if (!waiters) {
            return;
        }
        waiters.forEach((entry) => {
            if (entry.timer) {
                clearTimeout(entry.timer);
            }
            entry.resolve(value);
        });
        this.#serviceWaiters.delete(name);
    }

    #rejectWaiters(name: string, error: Error): void {
        const waiters = this.#serviceWaiters.get(name);
        if (!waiters) {
            return;
        }
        waiters.forEach((entry) => {
            if (entry.timer) {
                clearTimeout(entry.timer);
            }
            entry.reject(error);
        });
        this.#serviceWaiters.delete(name);
    }

    register<TServiceName extends SoAIServiceId>(name: TServiceName, instance: SoAIServiceRegistry[TServiceName], metadata?: Partial<ServiceMetadata>): this;
    register(name: string, instance: SoAIRegisteredService, metadata?: Partial<ServiceMetadata>): this;
    register(name: string, instance: SoAIRegisteredService, metadata: Partial<ServiceMetadata> = {}): this {
        const normalizedName = normalizeServiceName(name);
        if (!instance) {
            throw new Error(`Service instance is required for ${name}`);
        }
        if (this.#services.has(normalizedName)) {
            if (this.#services.get(normalizedName) === instance) {
                return this;
            }
            throw new Error(`Service ${normalizedName} is already registered`);
        }
        this.#services.set(normalizedName, instance);
        this.#serviceMetadata.set(normalizedName, {
            registeredAt: Date.now(),
            initialized: false,
            ...metadata
        });
        this.#resolveWaiters(normalizedName, instance);
        return this;
    }

    unregister(name: string): boolean {
        const normalizedName = normalizeServiceName(name);
        const removed = this.#services.delete(normalizedName);
        this.#serviceMetadata.delete(normalizedName);
        this.#pendingInitializations.delete(normalizedName);
        return removed;
    }

    get<TServiceName extends SoAIServiceId>(name: TServiceName): SoAIServiceRegistry[TServiceName];
    get(name: string): SoAIRegisteredService;
    get(name: string): SoAIRegisteredService {
        const normalizedName = normalizeServiceName(name);
        const instance = this.#services.get(normalizedName);
        if (!instance) {
            throw new Error(`Service ${normalizedName} is not registered`);
        }
        return instance;
    }

    has(name: string): boolean {
        if (!isString(name)) {
            return false;
        }
        const token = name.trim();
        if (!token) {
            return false;
        }
        if (!isCanonicalServiceId(token)) {
            throw new Error(`Service id must be canonical (core.*, features.*, pages.*). Got '${token}'`);
        }
        return this.#services.has(token);
    }

    initialize<TServiceName extends SoAIServiceId>(name: TServiceName): Promise<SoAIServiceRegistry[TServiceName] | null>;
    initialize(name: string): Promise<SoAIRegisteredService | null>;
    async initialize(name: string): Promise<SoAIRegisteredService | null> {
        const normalizedName = normalizeServiceName(name);
        const metadata = this.#serviceMetadata.get(normalizedName);
        if (!metadata) {
            throw new Error(`Service ${normalizedName} is not registered`);
        }
        if (metadata.initialized) {
            return this.get(normalizedName);
        }
        if (this.#pendingInitializations.has(normalizedName)) {
            return this.#pendingInitializations.get(normalizedName) ?? null;
        }
        const instance = this.#services.get(normalizedName);
        if (!instance) {
            throw new Error(`Service ${normalizedName} instance not found`);
        }
        if (!isInitializableService(instance)) {
            metadata.initialized = true;
            return instance;
        }
        const initializePromise = (async () => {
            try {
                await Promise.resolve(instance.initialize());
                metadata.initialized = true;
                metadata.initializedAt = Date.now();
                return instance;
            } finally {
                this.#pendingInitializations.delete(normalizedName);
            }
        })();
        this.#pendingInitializations.set(normalizedName, initializePromise);
        return initializePromise;
    }

    ensureInitialized<TServiceName extends SoAIServiceId>(name: TServiceName): Promise<SoAIServiceRegistry[TServiceName] | null>;
    ensureInitialized(name: string): Promise<SoAIRegisteredService | null>;
    async ensureInitialized(name: string): Promise<SoAIRegisteredService | null> {
        const normalizedName = normalizeServiceName(name);
        const metadata = this.#serviceMetadata.get(normalizedName);
        if (metadata?.initialized) {
            return this.get(normalizedName);
        }
        return this.initialize(normalizedName);
    }

    getAll(): ServiceInfo[] {
        return Array.from(this.#services.entries()).map(([name, instance]) => ({
            name,
            instance,
            metadata: this.#serviceMetadata.get(name)
        }));
    }

    isInitialized(name: string): boolean {
        const normalizedName = normalizeServiceName(name);
        const metadata = this.#serviceMetadata.get(normalizedName);
        return metadata?.initialized ?? false;
    }

    markUninitialized(name: string): void {
        const normalizedName = normalizeServiceName(name);
        const metadata = this.#serviceMetadata.get(normalizedName);
        if (!metadata) {
            throw new Error(`Service ${normalizedName} is not registered`);
        }
        metadata.initialized = false;
        delete metadata.initializedAt;
        this.#pendingInitializations.delete(normalizedName);
    }

    async initializeAll(names: string[] | null = null): Promise<InitializeResult[]> {
        const targetServices = names ?? Array.from(this.#services.keys());
        const initializeTasks = targetServices.map((name) => {
            if (this.isInitialized(name)) {
                return Promise.resolve({ name, skipped: true });
            }
            const initializeService = async (): Promise<InitializeResult> => {
                try {
                    await this.initialize(name);
                    return { name, initialized: true };
                } catch (error) {
                    throw ensureError(error);
                }
            };
            return initializeService();
        });
        return Promise.all(initializeTasks);
    }

    clear(): void {
        this.#services.clear();
        this.#serviceMetadata.clear();
        this.#pendingInitializations.clear();
        this.#serviceWaiters.forEach((_unusedValue, name) => {
            this.#rejectWaiters(name, new Error('Service container cleared'));
        });
        this.#serviceWaiters.clear();
    }

    waitFor<TServiceName extends SoAIServiceId>(name: TServiceName, options?: WaitForOptions): Promise<SoAIServiceRegistry[TServiceName]>;
    waitFor(name: string, options?: WaitForOptions): Promise<SoAIRegisteredService>;
    waitFor(name: string, options: WaitForOptions = {}): Promise<SoAIRegisteredService> {
        const normalizedName = normalizeServiceName(name);
        if (this.#services.has(normalizedName)) {
            return Promise.resolve(this.get(normalizedName));
        }
        const rawTimeoutMs = options.timeoutMs;
        const timeoutMs = typeof rawTimeoutMs === 'number' && Number.isFinite(rawTimeoutMs) && rawTimeoutMs > 0 ? rawTimeoutMs : null;
        return new Promise((resolve, reject) => {
            const entry: WaiterEntry = { resolve, reject, timer: null };
            const cleanup = (): void => {
                const waiters = this.#serviceWaiters.get(normalizedName);
                if (!waiters) {
                    return;
                }
                waiters.delete(entry);
                if (!waiters.size) {
                    this.#serviceWaiters.delete(normalizedName);
                }
            };
            if (timeoutMs !== null) {
                entry.timer = setTimeout(() => {
                    cleanup();
                    reject(new Error(`Service ${normalizedName} not ready within ${timeoutMs}ms`));
                }, timeoutMs);
            }
            const wrappedResolve = (value: SoAIRegisteredService): void => {
                cleanup();
                resolve(value);
            };
            const wrappedReject = (error: Error): void => {
                cleanup();
                reject(error);
            };
            entry.resolve = wrappedResolve;
            entry.reject = wrappedReject;
            const waiters = this.#serviceWaiters.get(normalizedName) ?? new Set<WaiterEntry>();
            waiters.add(entry);
            this.#serviceWaiters.set(normalizedName, waiters);
        });
    }
}

let defaultServiceContainer: ServiceContainer | null = null;

const getServiceContainer = (): ServiceContainer => {
    if (!defaultServiceContainer) {
        defaultServiceContainer = new ServiceContainer();
    }
    return defaultServiceContainer;
};

export { ServiceContainer, getServiceContainer };
