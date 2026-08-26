/* SoAI - Shared realtime resource subscriptions [frontend/assets/ts/core/realtime/resourceSubscriptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { runCleanupCallbacks } from '@core/lifecycle/cleanup.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ResourceStreamBinding {
    resource: string;
    handler: (value: JsonValue | null) => void;
}

interface ResourceStreamSubscription {
    dispose: () => void;
}

interface ResourceStreamBatchOptions {
    label: string;
    bindings: readonly ResourceStreamBinding[];
    subscribeToData: (resource: string, handler: (value: JsonValue | null) => void) => (() => void) | null;
}

const createResourceStreamSubscription = (disposer: () => void): ResourceStreamSubscription => {
    let disposed = false;
    return {
        dispose: (): void => {
            if (disposed) {
                return;
            }
            disposed = true;
            disposer();
        }
    };
};

const disposeResourceStreamSubscriptions = (subscriptions: readonly ResourceStreamSubscription[]): void => {
    let firstError: Error | null = null;
    runCleanupCallbacks(
        subscriptions.map((subscription) => subscription.dispose),
        (runtimeError) => {
            firstError = firstError ?? runtimeError;
        }
    );
    if (firstError) {
        throw firstError;
    }
};

const subscribeResourceStateStreamBatch = (options: ResourceStreamBatchOptions): ResourceStreamSubscription[] => {
    const subscriptions: ResourceStreamSubscription[] = [];
    try {
        for (const binding of options.bindings) {
            const disposer = options.subscribeToData(binding.resource, binding.handler);
            if (!isFunction(disposer)) {
                throw new Error(`${options.label} stream "${binding.resource}" must return an unsubscribe function`);
            }
            subscriptions.push(createResourceStreamSubscription(disposer));
        }
        return subscriptions;
    } catch (error) {
        try {
            disposeResourceStreamSubscriptions(subscriptions);
        } catch (cleanupError) {
            throw new AggregateError([ensureError(error), ensureError(cleanupError)], `${options.label} stream subscription failed and cleanup also failed`);
        }
        throw ensureError(error);
    }
};

export { disposeResourceStreamSubscriptions, subscribeResourceStateStreamBatch };
export type { ResourceStreamBatchOptions, ResourceStreamBinding, ResourceStreamSubscription };
