/* SoAI - Shared resource contracts [frontend/assets/ts/core/resources.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ResourceTracker, safeDispose } from '@core/resourcetracker/service.ts';
import type { DisposableResource } from '@core/resourcetracker/types.ts';
import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';

type CleanupFunction = (resource: DisposableResource) => void | Promise<void>;
type CleanupHandler = () => void | Promise<void>;

interface ResourceEntry {
    resource: DisposableResource;
    cleanup: CleanupFunction;
    timestamp: number;
    cleanedUp: boolean;
}

class CleanupManager {
    activeResources: Map<string, ResourceEntry>;
    cleanupHandlers: Set<CleanupHandler>;
    isCleaningUp: boolean;
    cleanupTimeoutMs: number;
    forcedCleanupTimeoutMs: number;

    constructor() {
        this.activeResources = new Map();
        this.cleanupHandlers = new Set();
        this.isCleaningUp = false;
        this.cleanupTimeoutMs = 5000;
        this.forcedCleanupTimeoutMs = 10000;
    }

    async registerResource(id: string, resource: DisposableResource, cleanupFunctionValue: CleanupFunction | null = null): Promise<boolean> {
        if (this.isCleaningUp) {
            return false;
        }

        const existingResource = this.activeResources.get(id);
        if (existingResource) {
            try {
                if (isFunction(existingResource.cleanup)) {
                    await Promise.resolve(existingResource.cleanup(existingResource.resource));
                }
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('Resources', 'Existing resource cleanup failed', runtimeError);
                safeDispose(existingResource.resource);
            }
        }

        this.activeResources.set(id, {
            resource,
            cleanup: cleanupFunctionValue || this.#defaultCleanup,
            timestamp: Date.now(),
            cleanedUp: false
        });

        return true;
    }

    unregisterResource(id: string): boolean {
        return this.activeResources.delete(id);
    }

    async cleanupResource(id: string): Promise<boolean> {
        const entry = this.activeResources.get(id);
        if (!entry || entry.cleanedUp) {
            return false;
        }

        entry.cleanedUp = true;

        try {
            if (isFunction(entry.cleanup)) {
                await Promise.resolve(entry.cleanup(entry.resource));
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('Resources', 'Cleanup resource handler failed', runtimeError);
            safeDispose(entry.resource);
        }

        this.activeResources.delete(id);
        return true;
    }

    async cleanupAll(): Promise<void> {
        if (this.isCleaningUp) {
            return;
        }

        this.isCleaningUp = true;

        try {
            await withTimeout(this.#performCleanup(), { timeoutMs: this.cleanupTimeoutMs, timeoutMessage: 'Cleanup timeout' });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('Resources', 'Cleanup all promise failed', runtimeError);
            await this.#forceCleanup();
        }

        this.isCleaningUp = false;
    }

    async #performCleanup(): Promise<void> {
        const cleanupPromises: Promise<void>[] = [];

        for (const entry of this.activeResources.values()) {
            const runCleanup = async (): Promise<void> => {
                try {
                    if (isFunction(entry.cleanup)) {
                        await entry.cleanup(entry.resource);
                    }
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.warn('Resources', 'Performing cleanup failed', runtimeError);
                    safeDispose(entry.resource);
                }
            };
            const promise = runCleanup();
            cleanupPromises.push(promise);
        }

        await Promise.allSettled(cleanupPromises);
        this.activeResources.clear();

        const handlerPromises: Promise<void>[] = [];
        for (const handler of this.cleanupHandlers) {
            const task = (async (): Promise<void> => {
                try {
                    await handler();
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.warn('Resources', 'Cleanup handler failed', runtimeError);
                }
            })();
            handlerPromises.push(task);
        }

        await Promise.allSettled(handlerPromises);
    }

    async #forceCleanup(): Promise<void> {
        try {
            await withTimeout(this.#performForceCleanup(), { timeoutMs: this.forcedCleanupTimeoutMs, timeoutMessage: 'Cleanup timeout' });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('Resources', 'Force cleanup promise failed', runtimeError);
            this.#emergencyCleanup();
        }
    }

    async #performForceCleanup(): Promise<void> {
        for (const entry of this.activeResources.values()) {
            try {
                safeDispose(entry.resource);
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('ResourceTracker', 'Failed to dispose active resource', runtimeError);
            }
        }
        this.activeResources.clear();

        for (const handler of this.cleanupHandlers) {
            try {
                await Promise.resolve(handler());
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('ResourceTracker', 'Cleanup handler failed', runtimeError);
            }
        }
    }

    #emergencyCleanup(): void {
        this.activeResources.clear();
        this.cleanupHandlers.clear();
    }

    #defaultCleanup = (resource: DisposableResource): void => {
        safeDispose(resource);
    };

    addCleanupHandler(handler: CleanupHandler): () => void {
        if (isFunction(handler)) {
            this.cleanupHandlers.add(handler);
            return () => this.cleanupHandlers.delete(handler);
        }
        return () => {};
    }

    removeCleanupHandler(handler: CleanupHandler): boolean {
        return this.cleanupHandlers.delete(handler);
    }

    isResourceRegistered(id: string): boolean {
        return this.activeResources.has(id);
    }

    getResourceCount(): number {
        return this.activeResources.size;
    }

    clear(): void {
        this.activeResources.clear();
        this.cleanupHandlers.clear();
        this.isCleaningUp = false;
    }
}

const Resources = {
    ResourceTracker,
    CleanupManager,
    safeDispose
};

let cleanupManagerInstance: CleanupManager | null = null;

const getCleanupManager = (): CleanupManager => {
    if (cleanupManagerInstance === null) {
        cleanupManagerInstance = new CleanupManager();
    }
    return cleanupManagerInstance;
};

const resetCleanupManager = (): void => {
    if (!cleanupManagerInstance) {
        return;
    }
    cleanupManagerInstance.clear();
    cleanupManagerInstance = null;
};

export { ResourceTracker, CleanupManager, safeDispose, Resources, getCleanupManager, resetCleanupManager };
