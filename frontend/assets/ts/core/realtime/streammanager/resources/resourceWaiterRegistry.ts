/* SoAI - Per-caller resource reconciliation waiter ownership [frontend/assets/ts/core/realtime/streammanager/resources/resourceWaiterRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError } from '@core/errors/abort.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import type { ResourceWaiter } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

class ResourceWaiterRegistry {
    readonly #waiters = new Set<ResourceWaiter>();

    create(targetRevision: number, signal: AbortSignal | null): Promise<JsonValue | null> {
        const deferred = createDeferred<JsonValue | null>();
        const waiter: ResourceWaiter = {
            targetReconciliationRevision: targetRevision,
            deferred,
            signal,
            abortListener: null
        };
        this.#waiters.add(waiter);
        if (signal) {
            waiter.abortListener = (): void => {
                if (!this.#waiters.has(waiter)) return;
                this.#remove(waiter);
                deferred.reject(createAbortError());
            };
            signal.addEventListener('abort', waiter.abortListener, { once: true });
            if (signal.aborted) waiter.abortListener();
        }
        return deferred.promise;
    }

    resolve(committedRevision: number, value: JsonValue | null): void {
        for (const waiter of [...this.#waiters]) {
            if (waiter.targetReconciliationRevision > committedRevision) continue;
            this.#remove(waiter);
            waiter.deferred.resolve(value);
        }
    }

    reject(error: Error, throughRevision: number | null = null): void {
        for (const waiter of [...this.#waiters]) {
            if (throughRevision !== null && waiter.targetReconciliationRevision > throughRevision) continue;
            this.#remove(waiter);
            waiter.deferred.reject(error);
        }
    }

    cancel(message: string, reason: string): void {
        this.reject(new LifecycleCancellationError(message, reason));
    }

    get size(): number {
        return this.#waiters.size;
    }

    #remove(waiter: ResourceWaiter): void {
        this.#waiters.delete(waiter);
        if (waiter.signal && waiter.abortListener) waiter.signal.removeEventListener('abort', waiter.abortListener);
    }
}

export { ResourceWaiterRegistry };
