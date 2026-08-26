/* SoAI - Shared runtime window identity [frontend/assets/ts/core/runtime/windowIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { ensureError } from '@core/errors/coerce.ts';

const STORAGE_KEY = 'soai.window.identity';
const QUERY_PARAMETER = 'windowId';
const MAX_IDENTITY_LENGTH = 64;
const VALID_IDENTITY_PATTERN = /^[a-zA-Z0-9_-]+$/;

interface GlobalScopeInterface {
    sessionStorage?:
        | {
              getItem: (key: string) => string | null;
              setItem: (key: string, value: string) => void;
          }
        | undefined;
    location?:
        | {
              pathname: string;
              search?: string | undefined;
              hash?: string | undefined;
          }
        | undefined;
    history?:
        | {
              replaceState: (data: JsonValue | null | undefined, unused: string, url?: string | null | undefined) => void;
          }
        | undefined;
}

type StorageContract = {
    getItem: (key: string) => string | null;
    setItem: (key: string, value: string) => void;
};

class WindowIdentityService {
    private readonly scope: GlobalScopeInterface;
    private identity: string | null;
    private detached: boolean;
    private readyPromise: Promise<string>;

    constructor(scope: GlobalScopeInterface = globalThis) {
        this.scope = scope;
        this.identity = null;
        this.detached = false;
        this.readyPromise = Promise.resolve('');
        this.initialize();
    }

    private initialize(): string {
        const scope = this.resolveScope();
        const storage = this.resolveSessionStorage(scope);
        const location = this.resolveLocation(scope);
        const history = this.resolveHistory(scope);
        const isDetached = this.detectDetachedContext(location);
        const parameters = new URLSearchParams(location.search ?? '');
        const queryId = this.readQueryIdentity(parameters);
        if (storage === null) {
            const identity = isDetached && queryId ? queryId : this.generateId();
            this.identity = identity;
            this.detached = isDetached;
            this.readyPromise = Promise.resolve(identity);
            return identity;
        }
        const storedId = this.readStoredIdentity(storage);
        let identity = storedId;
        if (isDetached) {
            identity = queryId || identity || this.generateId();
        } else if (!identity) {
            identity = this.generateId();
        }
        this.persistIdentity(storage, identity);
        this.identity = identity;
        this.detached = isDetached;
        if (isDetached) {
            this.ensureDetachedQuery(identity, parameters, location, history);
        } else if (parameters.has(QUERY_PARAMETER)) {
            parameters.delete(QUERY_PARAMETER);
            this.replaceUrl(parameters, location, history);
        }
        this.readyPromise = Promise.resolve(identity);
        return identity;
    }

    ready(): Promise<string> {
        return this.readyPromise;
    }

    async get(): Promise<string> {
        await this.ready();
        return this.current();
    }

    current(): string {
        if (!isString(this.identity) || !this.identity) {
            throw new Error('Window identity is not ready');
        }
        return this.identity;
    }

    isDetachedContext(): boolean {
        return this.detached;
    }

    createDetachedIdentity(): string {
        return this.generateId();
    }

    private resolveScope(): GlobalScopeInterface {
        if (!isObject(this.scope)) {
            throw new Error('Global scope is unavailable for window identity');
        }
        return this.scope;
    }

    private resolveSessionStorage(scope: GlobalScopeInterface): StorageContract | null {
        try {
            const storage = scope.sessionStorage;
            if (!storage || !isFunction(storage.getItem) || !isFunction(storage.setItem)) {
                return null;
            }
            return storage;
        } catch (error) {
            throw ensureError(error);
        }
    }

    private resolveLocation(scope: GlobalScopeInterface): NonNullable<GlobalScopeInterface['location']> {
        if (!scope.location) {
            throw new Error('Location is required for window identity');
        }
        return scope.location;
    }

    private resolveHistory(scope: GlobalScopeInterface): NonNullable<GlobalScopeInterface['history']> {
        const history = scope.history;
        if (!history || !isFunction(history.replaceState)) {
            throw new Error('History API is required for window identity');
        }
        return history;
    }

    private detectDetachedContext(location: NonNullable<GlobalScopeInterface['location']>): boolean {
        const pathname = isString(location.pathname) ? location.pathname : '';
        if (pathname === '/' || pathname === '') {
            return false;
        }
        return pathname.endsWith('/detached.html') || pathname === '/detached.html';
    }

    private isValidIdentityFormat(value: string): boolean {
        if (!isString(value)) {
            return false;
        }
        const trimmed = value.trim();
        if (!trimmed || trimmed.length > MAX_IDENTITY_LENGTH) {
            return false;
        }
        return VALID_IDENTITY_PATTERN.test(trimmed);
    }

    private readQueryIdentity(parameters: URLSearchParams): string | null {
        const value = parameters.get(QUERY_PARAMETER);
        if (!isString(value)) {
            return null;
        }
        const normalized = value.trim();
        if (!normalized || !this.isValidIdentityFormat(normalized)) {
            return null;
        }
        return normalized;
    }

    private readStoredIdentity(storage: StorageContract): string | null {
        try {
            const value = storage.getItem(STORAGE_KEY);
            if (!isString(value)) {
                return null;
            }
            const normalized = value.trim();
            if (!normalized || !this.isValidIdentityFormat(normalized)) {
                return null;
            }
            return normalized;
        } catch (error) {
            throw ensureError(error);
        }
    }

    private generateId(): string {
        const identity = generateSecureId({ format: 'hex' });
        if (!/^[a-f0-9]{32}$/.test(identity)) {
            throw new Error('Window identity must be a 32-character hexadecimal string');
        }
        return identity;
    }

    private persistIdentity(storage: StorageContract, identity: string): void {
        if (!this.isValidIdentityFormat(identity)) {
            throw new Error('Window identity must be alphanumeric (max 64 chars)');
        }
        try {
            storage.setItem(STORAGE_KEY, identity.trim());
        } catch (error) {
            throw ensureError(error);
        }
    }

    private ensureDetachedQuery(identity: string, parameters: URLSearchParams, location: NonNullable<GlobalScopeInterface['location']>, history: NonNullable<GlobalScopeInterface['history']>): void {
        if (parameters.get(QUERY_PARAMETER) === identity) {
            return;
        }
        parameters.set(QUERY_PARAMETER, identity);
        this.replaceUrl(parameters, location, history);
    }

    private replaceUrl(parameters: URLSearchParams, location: NonNullable<GlobalScopeInterface['location']>, history: NonNullable<GlobalScopeInterface['history']>): void {
        const search = parameters.toString();
        const hash = isString(location.hash) ? location.hash : '';
        const next = `${location.pathname}${search ? `?${search}` : ''}${hash}`;
        history.replaceState(null, '', next);
    }
}

interface WindowIdentityAccessor {
    resolve: () => WindowIdentityService;
}

const createWindowIdentityAccessor = (): WindowIdentityAccessor => {
    let instance: WindowIdentityService | null = null;
    return {
        resolve(): WindowIdentityService {
            if (!instance) {
                instance = new WindowIdentityService();
            }
            return instance;
        }
    };
};

const singleton = createWindowIdentityAccessor();

interface WindowIdentityAPI {
    ready: () => Promise<string>;
    get: () => Promise<string>;
    current: () => string;
    isDetachedContext: () => boolean;
    createDetachedIdentity: () => string;
}

const windowIdentity: WindowIdentityAPI = {
    ready: () => singleton.resolve().ready(),
    get: () => singleton.resolve().get(),
    current: () => singleton.resolve().current(),
    isDetachedContext: () => singleton.resolve().isDetachedContext(),
    createDetachedIdentity: () => singleton.resolve().createDetachedIdentity()
};

export { WindowIdentityService, windowIdentity };

export type { WindowIdentityAPI, GlobalScopeInterface };
