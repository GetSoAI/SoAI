/* SoAI - Plugins feature backend task stream ports [frontend/assets/ts/features/plugins/modals/backend/backendStreamPorts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import type { PageStreamingContract } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { StreamHandlerCallbacks } from '@core/routing/pages/pagetypes/public.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { BackendOperationHost, BackendTaskActionOptions, BackendTaskCommandOptions } from '@features/plugins/modals/backend/backendTypes.ts';
import type { DownloadManagerHost } from '@features/plugins/modals/downloadmanager/contracts.ts';

interface BackendStreamPorts {
    createStreamHandlers: BackendOperationHost['createStreamHandlers'];
    trackAcceptedTask: DownloadManagerHost['execution']['trackAcceptedTask'];
    startTaskAction: BackendOperationHost['startTaskAction'];
    startTaskCommand: BackendOperationHost['startTaskCommand'];
}

const normalizeOperationMeta = (operation: BackendTaskActionOptions['operation'] | BackendTaskCommandOptions['operation'] | null | undefined): JsonObject | null => {
    if (operation === null || operation === undefined) return null;
    const value = toJsonCompatibleValue(operation);
    if (!isJsonObject(value)) {
        throw new Error('Plugin task operation metadata must be a JSON object');
    }
    return value;
};

const normalizeBackendTaskActionOptions = (options: BackendTaskActionOptions): { method?: string; body?: JsonValue | null | undefined; handlers?: BackendTaskActionOptions['handlers']; operation?: JsonObject | null } => ({
    ...(options.method === undefined ? {} : { method: options.method }),
    ...(options.body === undefined ? {} : { body: options.body }),
    handlers: options.handlers,
    operation: normalizeOperationMeta(options.operation)
});

const normalizeBackendTaskCommandOptions = (options: BackendTaskCommandOptions): { handlers?: BackendTaskCommandOptions['handlers']; operation?: JsonObject | null } => ({
    handlers: options.handlers,
    operation: normalizeOperationMeta(options.operation)
});

const normalizeModalStreamCallbacks = (callbacks: { onProgress?: (data: JsonValue | undefined) => void; onComplete?: (data: JsonValue | undefined) => void; onError?: (error: Error) => void } | undefined): StreamHandlerCallbacks | undefined => {
    if (!callbacks) return undefined;
    return {
        ...(callbacks.onProgress ? { onProgress: (data: JsonValue | null): void => callbacks.onProgress?.(data ?? undefined) } : {}),
        ...(callbacks.onComplete ? { onComplete: (data: JsonValue | null): void => callbacks.onComplete?.(data ?? undefined) } : {}),
        ...(callbacks.onError ? { onError: (error: Error | JsonValue | null): void => callbacks.onError?.(ensureError(error)) } : {})
    };
};

const createBackendStreamPorts = (streaming: PageStreamingContract): BackendStreamPorts => ({
    createStreamHandlers: (_key, _message, callbacks) => streaming.handlers(normalizeModalStreamCallbacks(callbacks)),
    trackAcceptedTask: (taskId, options) =>
        streaming.runtime().tasks.trackAcceptedTask(taskId, {
            handlers: options.handlers,
            operation: normalizeOperationMeta(options.operation),
            ...(options.timeoutMs === undefined ? {} : { timeoutMs: options.timeoutMs })
        }),
    startTaskAction: (endpoint, options, runtimeOptions) => streaming.taskAction(endpoint, normalizeBackendTaskActionOptions(options), runtimeOptions),
    startTaskCommand: (command, options, runtimeOptions) => {
        if (!isJsonObject(command)) {
            throw new Error('Plugin task command must be JSON');
        }
        return streaming.taskCommand(command, normalizeBackendTaskCommandOptions(options), runtimeOptions);
    }
});

export { createBackendStreamPorts };
export type { BackendStreamPorts };
