/* SoAI - Shared runtime environment events [frontend/assets/ts/core/runtimeenv/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { collectDetachedContext, prepareDetachedContextForPage, safeReleaseWindowRecord, takePendingWindowMetadata } from '@core/runtimeenv/actions.ts';
import type { DetachedWindowCoordinator } from '@core/runtimeenv/coordinator.ts';
import type { RuntimeWindowServiceState, StateManagerInterface } from '@core/runtimeenv/internalContracts.ts';
import { isValidRuntimeString, parseDetachedContextPayload, serializeDetachedContext, trimRuntimeString, validateWindowIdentifier } from '@core/runtimeenv/mappers.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface RuntimeEnvLogger {
    logDetachedWarning: (message: string, details?: TelemetryValue) => void;
}

interface WindowServiceEventDependencies extends RuntimeEnvLogger {
    state: RuntimeWindowServiceState;
    isPrimaryWindow: boolean;
    hostWindowId: string;
    coordinator: DetachedWindowCoordinator | null;
    closeCurrentWindow: () => void;
    ensureStateManager: () => StateManagerInterface;
    trackAsyncTask: (task: Promise<void> | undefined, contextMessage: string) => void;
    warmDetachedBundle: () => Promise<void>;
    warmLogBundle: () => Promise<void>;
    clearInterval: (id: number) => void;
}

const resolveEventWindowId = (source: JsonValue, payloadWindowId: JsonValue, dependencies: RuntimeEnvLogger, message: string, details: JsonObject): string | null => {
    const payloadId = isValidRuntimeString(payloadWindowId) ? trimRuntimeString(payloadWindowId) : null;
    const sourceId = isValidRuntimeString(source) ? trimRuntimeString(source) : null;
    const windowId = payloadId ?? sourceId;
    if (!windowId) {
        dependencies.logDetachedWarning(message, details);
        return null;
    }
    return windowId;
};

const flushPendingDetachedContextState = (dependencies: WindowServiceEventDependencies): void => {
    const pendingContext = dependencies.state.pendingContext;
    if (!pendingContext) {
        dependencies.logDetachedWarning('Detached context flush requires pending state');
        return;
    }

    let manager: StateManagerInterface;
    try {
        manager = dependencies.ensureStateManager();
    } catch (error) {
        const runtimeError = ensureError(error);
        dependencies.logDetachedWarning('State manager unavailable while flushing detached context', runtimeError);
        throw ensureError(error);
    }

    const snapshot = pendingContext.state;
    if (!isObject(snapshot)) {
        dependencies.logDetachedWarning('Detached context snapshot must be an object', { snapshot });
        dependencies.state.pendingContext = null;
        return;
    }

    for (const [key, value] of Object.entries(snapshot)) {
        try {
            manager.setTabState(key, value);
        } catch (error) {
            const runtimeError = ensureError(error);
            dependencies.logDetachedWarning('Failed to sync detached state entry', { key, error: runtimeError });
        }
    }

    dependencies.state.pendingContext = null;
    if (dependencies.state.contextDeferred) {
        if (!isFunction(dependencies.state.contextDeferred.resolve)) {
            dependencies.logDetachedWarning('Detached context deferred resolver is missing');
        } else {
            dependencies.state.contextDeferred.resolve(true);
        }
        dependencies.state.contextDeferred = null;
    }
    if (!dependencies.state.contextPromise) {
        dependencies.state.contextPromise = Promise.resolve(true);
    }
};

const handleDetachedContextEvent = (source: JsonValue, payload: JsonValue, dependencies: WindowServiceEventDependencies): void => {
    if (dependencies.isPrimaryWindow) {
        dependencies.logDetachedWarning('Primary window cannot process detached context payloads', { payload });
        return;
    }

    const sourceId = validateWindowIdentifier(source, 'Detached context handling', dependencies);
    if (!sourceId) {
        return;
    }
    if (sourceId !== dependencies.hostWindowId) {
        dependencies.logDetachedWarning('Detached context payload rejected: unexpected source', {
            source: sourceId,
            expected: dependencies.hostWindowId
        });
        return;
    }
    if (!isObject(payload)) {
        dependencies.logDetachedWarning('Detached context payload must be an object', { payload });
        return;
    }

    const parsedContext = parseDetachedContextPayload(payload, dependencies);
    if (!parsedContext) {
        dependencies.logDetachedWarning('Detached context payload is invalid', { payload });
        return;
    }
    dependencies.state.detachedContext = parsedContext;
    dependencies.state.pendingContext = parsedContext;
    flushPendingDetachedContextState(dependencies);
};

const handleDetachedReadyEvent = (source: string, payload: JsonObject | undefined = {}, dependencies: WindowServiceEventDependencies): void => {
    if (!dependencies.isPrimaryWindow) {
        return;
    }
    if (!isObject(payload)) {
        dependencies.logDetachedWarning('Detached ready payload must be an object', { payload });
        return;
    }

    const windowId = resolveEventWindowId(source, payload['windowId'] ?? null, dependencies, 'Detached ready event requires a windowId', { payload, source });
    if (!windowId) {
        return;
    }

    const metadata = takePendingWindowMetadata(dependencies.state, windowId, dependencies);
    if (!metadata) {
        dependencies.logDetachedWarning('Detached ready event is missing metadata', { windowId });
        return;
    }

    if (!dependencies.state.openWindows.has(windowId)) {
        dependencies.state.openWindows.set(windowId, {
            window: null,
            pageId: metadata.pageId,
            openedAt: Date.now(),
            monitorId: null,
            metadata
        });
    }

    prepareDetachedContextForPage(metadata.pageId, {
        logDetachedWarning: dependencies.logDetachedWarning,
        trackAsyncTask: dependencies.trackAsyncTask,
        warmLogBundle: dependencies.warmLogBundle
    });
    dependencies.trackAsyncTask(dependencies.warmDetachedBundle(), 'Detached bundle warmup failed');

    const context = collectDetachedContext(windowId, metadata, {
        logDetachedWarning: dependencies.logDetachedWarning,
        ensureStateManager: dependencies.ensureStateManager
    });
    if (!context) {
        return;
    }
    if (!dependencies.coordinator) {
        dependencies.logDetachedWarning('Detached window coordinator is unavailable for context dispatch', {
            windowId
        });
        return;
    }

    dependencies.coordinator.send('detached-context', serializeDetachedContext(context), windowId);
};

const handleDetachedTeardownEvent = (source: string, payload: JsonObject | undefined = {}, dependencies: WindowServiceEventDependencies): void => {
    if (!isObject(payload)) {
        dependencies.logDetachedWarning('Detached teardown payload must be an object', { payload });
        return;
    }

    const windowId = resolveEventWindowId(source, payload['windowId'] ?? null, dependencies, 'Detached teardown requires a windowId', { payload, source });
    if (!windowId) {
        return;
    }

    if (!dependencies.state.openWindows.has(windowId) && !dependencies.state.pendingMetadata.has(windowId)) {
        return;
    }
    safeReleaseWindowRecord(dependencies.state, windowId, {
        clearInterval: dependencies.clearInterval,
        logDetachedWarning: dependencies.logDetachedWarning
    });
};

const handleDetachedCloseRequestEvent = (source: JsonValue, payload: JsonValue, dependencies: WindowServiceEventDependencies): void => {
    if (dependencies.isPrimaryWindow) {
        return;
    }
    const sourceId = validateWindowIdentifier(source, 'Detached close request handling', dependencies);
    if (!sourceId) {
        return;
    }
    if (sourceId !== dependencies.hostWindowId) {
        dependencies.logDetachedWarning('Detached close request rejected: unexpected source', {
            source: sourceId,
            expected: dependencies.hostWindowId
        });
        return;
    }
    if (!isJsonObject(payload)) {
        dependencies.logDetachedWarning('Detached close request payload must be an object', { payload });
        return;
    }
    const warningDetail: JsonObject = { payload };
    if (typeof source === 'string' || typeof source === 'number' || typeof source === 'boolean' || source === null) {
        warningDetail['source'] = source;
    }
    const windowId = resolveEventWindowId(source, payload['windowId'] ?? null, dependencies, 'Detached close request requires a windowId', warningDetail);
    if (!windowId || windowId !== dependencies.state.windowId) {
        dependencies.logDetachedWarning('Detached close request target mismatch', {
            requested: windowId,
            current: dependencies.state.windowId
        });
        return;
    }
    if (dependencies.coordinator) {
        dependencies.coordinator.send('detached-teardown', { windowId }, dependencies.hostWindowId);
    }
    dependencies.closeCurrentWindow();
};

export { flushPendingDetachedContextState, handleDetachedCloseRequestEvent, handleDetachedContextEvent, handleDetachedReadyEvent, handleDetachedTeardownEvent };
export type { WindowServiceEventDependencies };
