/* SoAI - Shared frontend maintenance coordinator [frontend/assets/ts/core/maintenanceCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

interface MaintenanceState {
    active: boolean;
    pausesTransport: boolean;
    reason: string | null;
    tokens: number;
    updatedAt: number;
}

type MaintenanceListener = (state: MaintenanceState) => void;
type MaintenanceMode = 'hold' | 'observe';

interface MaintenanceActivationOptions {
    mode?: MaintenanceMode;
}

interface MaintenanceEntry {
    mode: MaintenanceMode;
    reason: string | null;
}

interface SubscribeOptions {
    immediate?: boolean;
}

const normalizeReason = (value: string | null): string | null => {
    if (!isString(value)) {
        return null;
    }
    const trimmed = value.trim();
    return trimmed.length ? trimmed : null;
};

class MaintenanceCoordinator {
    private readonly tokens: Map<symbol, MaintenanceEntry>;
    private readonly listeners: Set<MaintenanceListener>;
    private state: MaintenanceState;

    constructor() {
        this.tokens = new Map();
        this.listeners = new Set();
        this.state = { active: false, pausesTransport: false, reason: null, tokens: 0, updatedAt: Date.now() };
    }

    isActive(): boolean {
        return this.state.active;
    }

    getState(): MaintenanceState {
        return { ...this.state };
    }

    #emit(): void {
        const snapshot = this.getState();
        this.listeners.forEach((listener) => {
            try {
                listener(snapshot);
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('MaintenanceCoordinator', 'Listener execution failed', runtimeError);
            }
        });
    }

    #updateState(): void {
        const entries = [...this.tokens.values()];
        const active = entries.length > 0;
        const reason = active ? (entries.at(-1)?.reason ?? null) : null;
        this.state = {
            active,
            pausesTransport: entries.some((entry) => entry.mode === 'hold'),
            reason,
            tokens: this.tokens.size,
            updatedAt: Date.now()
        };
        this.#emit();
    }

    activate(reason: string | null = null, options: MaintenanceActivationOptions = {}): symbol {
        const token = Symbol('maintenance');
        this.tokens.set(token, {
            mode: options.mode ?? 'hold',
            reason: normalizeReason(reason)
        });
        this.#updateState();
        return token;
    }

    deactivate(token: symbol | null = null): boolean {
        if (token) {
            this.tokens.delete(token);
        } else {
            this.tokens.clear();
        }
        this.#updateState();
        return this.tokens.size === 0;
    }

    subscribe(listener: MaintenanceListener, options: SubscribeOptions = {}): () => void {
        if (!isFunction(listener)) {
            throw new Error('Maintenance coordinator requires function listeners');
        }
        this.listeners.add(listener);
        const immediate = options.immediate !== false;
        if (immediate) {
            try {
                listener(this.getState());
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('MaintenanceCoordinator', 'Listener execution failed', runtimeError);
            }
        }
        return () => {
            this.listeners.delete(listener);
        };
    }
}

const MAINTENANCE_COORDINATOR_SERVICE_ID = 'core.maintenanceCoordinator';

const isMaintenanceCoordinator = <T>(value: T): value is T & MaintenanceCoordinator => {
    if (!isObject(value)) {
        return false;
    }
    return 'activate' in value && isFunction(value.activate) && 'deactivate' in value && isFunction(value.deactivate) && 'subscribe' in value && isFunction(value.subscribe) && 'getState' in value && isFunction(value.getState);
};

const createMaintenanceCoordinator = (): MaintenanceCoordinator => new MaintenanceCoordinator();

const getMaintenanceCoordinator = (): MaintenanceCoordinator => {
    const candidate = resolveKernelService(MAINTENANCE_COORDINATOR_SERVICE_ID);
    if (!isMaintenanceCoordinator(candidate)) {
        throw new Error(`${MAINTENANCE_COORDINATOR_SERVICE_ID} is not registered`);
    }
    return candidate;
};

export { getMaintenanceCoordinator, createMaintenanceCoordinator, MAINTENANCE_COORDINATOR_SERVICE_ID, MaintenanceCoordinator };

export type { MaintenanceActivationOptions, MaintenanceMode, MaintenanceState, MaintenanceListener, SubscribeOptions };
