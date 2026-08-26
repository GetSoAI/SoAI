/* SoAI - Shared runtime environment actions [frontend/assets/ts/core/runtimeenv/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { isNullOrUndefined, isNumber, isObject } from '@core/typeGuards.ts';
import type { DetachedContext, OpenWindowInfo, StateManagerInterface, WindowMetadata, WindowRecord } from '@core/runtimeenv/internalContracts.ts';
import { isValidRuntimeString, trimRuntimeString, validateWindowIdentifier } from '@core/runtimeenv/mappers.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface RuntimeEnvLogger {
    logDetachedWarning: (message: string, details?: TelemetryValue) => void;
}

interface MetadataStoreState {
    openWindows: Map<string, WindowRecord>;
    pendingMetadata: Map<string, WindowMetadata>;
}

interface ContextCollectionDependencies extends RuntimeEnvLogger {
    ensureStateManager: () => StateManagerInterface;
}

interface ReleaseDependencies extends RuntimeEnvLogger {
    clearInterval: (id: number) => void;
}

interface PagePreparationDependencies extends RuntimeEnvLogger {
    warmLogBundle: () => Promise<void>;
    trackAsyncTask: (task: Promise<void> | undefined, contextMessage: string) => void;
}

const getWindowRecordForAction = (state: MetadataStoreState, windowId: JsonValue, contextMessage: string, logger: RuntimeEnvLogger, options: { requireHandle?: boolean } = {}): { key: string; record: WindowRecord } | null => {
    const requireHandle = options.requireHandle !== false;
    const key = validateWindowIdentifier(windowId, contextMessage, logger);
    if (!key) {
        return null;
    }
    const record = state.openWindows.get(key);
    if (!isObject(record)) {
        logger.logDetachedWarning(`${contextMessage} requires a registered window`, { windowId: key });
        return null;
    }
    if (requireHandle && (!isObject(record.window) || !record.window)) {
        logger.logDetachedWarning(`${contextMessage} requires a valid window handle`, { windowId: key });
        return null;
    }
    return { key, record };
};

const storeWindowMetadata = (state: MetadataStoreState, windowId: JsonValue, metadata: WindowMetadata | null, logger: RuntimeEnvLogger): void => {
    if (!isValidRuntimeString(windowId)) {
        logger.logDetachedWarning('Detached metadata store requires a window identifier', { windowId });
        throw new TypeError('Detached metadata store requires a window identifier');
    }
    if (!metadata) {
        logger.logDetachedWarning('Detached window metadata must be an object', { metadata });
        throw new TypeError('Detached window metadata must be an object');
    }
    const key = trimRuntimeString(windowId);
    state.pendingMetadata.set(key, metadata);
    const record = state.openWindows.get(key);
    if (record) {
        record.metadata = metadata;
    }
};

const takePendingWindowMetadata = (state: MetadataStoreState, windowId: JsonValue, logger: RuntimeEnvLogger): WindowMetadata | null => {
    if (!isValidRuntimeString(windowId)) {
        logger.logDetachedWarning('Detached window metadata lookup requires a windowId', { windowId });
        return null;
    }
    const key = trimRuntimeString(windowId);
    if (state.pendingMetadata.has(key)) {
        const entry = state.pendingMetadata.get(key);
        if (!entry) {
            logger.logDetachedWarning('Detached window metadata entry is missing', { windowId: key });
            return null;
        }
        state.pendingMetadata.delete(key);
        return entry;
    }
    const record = state.openWindows.get(key);
    if (record?.metadata) {
        return record.metadata;
    }
    logger.logDetachedWarning('Detached window metadata missing', { windowId: key });
    return null;
};

const prepareDetachedContextForPage = (pageId: string | null | undefined, dependencies: PagePreparationDependencies): void => {
    if (isNullOrUndefined(pageId)) {
        return;
    }
    if (!isValidRuntimeString(pageId)) {
        dependencies.logDetachedWarning('Detached context preparation requires a pageId string', { pageId });
        return;
    }
    if (pageId.trim() === 'logs') {
        dependencies.trackAsyncTask(dependencies.warmLogBundle(), 'Detached log bundle warmup failed');
    }
};

const collectDetachedContext = (windowId: string, metadata: WindowMetadata, dependencies: ContextCollectionDependencies): DetachedContext | null => {
    if (!isValidRuntimeString(windowId)) {
        dependencies.logDetachedWarning('Detached context must include a windowId', { windowId });
        return null;
    }
    if (!isObject(metadata)) {
        dependencies.logDetachedWarning('Detached context metadata must be an object', { windowId, metadata });
        return null;
    }

    const manager = dependencies.ensureStateManager();
    const state = manager.snapshotTabState();
    if (!isObject(state)) {
        dependencies.logDetachedWarning('State manager snapshot must return an object', { state });
        return null;
    }
    const allowedKeys = new Set<string>(['core.storage.snapshot', 'core.auth.status']);
    const pageId = isValidRuntimeString(metadata.pageId) ? trimRuntimeString(metadata.pageId) : '';
    if (pageId === 'logs') {
        allowedKeys.add('stream.bundle.detached');
        allowedKeys.add('stream.bundle.logs');
    } else if (pageId === 'chat') {
        allowedKeys.add('stream.bundle.detached');
        allowedKeys.add('stream.bundle.catalog');
    } else if (pageId === 'hardware') {
        allowedKeys.add('stream.bundle.detached');
    }
    const filteredState: JsonObject = {};
    for (const [key, value] of Object.entries(state)) {
        if (allowedKeys.has(key)) {
            filteredState[key] = value;
        }
    }
    return {
        windowId: trimRuntimeString(windowId),
        metadata,
        timestamp: Date.now(),
        state: filteredState
    };
};

const releaseWindowRecord = (state: MetadataStoreState, windowId: string, dependencies: ReleaseDependencies): boolean => {
    const key = validateWindowIdentifier(windowId, 'Detached window release', dependencies);
    if (!key) {
        return false;
    }
    const entry = state.openWindows.get(key);
    if (!isObject(entry)) {
        dependencies.logDetachedWarning('Detached window release requires a registered window', { windowId: key });
        return false;
    }
    if (!isNullOrUndefined(entry.monitorId)) {
        if (!isNumber(entry.monitorId)) {
            dependencies.logDetachedWarning('Detached window monitor identifier is invalid', {
                windowId: key,
                monitorId: entry.monitorId
            });
        } else {
            dependencies.clearInterval(entry.monitorId);
        }
    }
    state.openWindows.delete(key);
    state.pendingMetadata.delete(key);
    return true;
};

const safeReleaseWindowRecord = (state: MetadataStoreState, windowId: string, dependencies: ReleaseDependencies): void => {
    try {
        releaseWindowRecord(state, windowId, dependencies);
    } catch (error) {
        const runtimeError = ensureError(error);
        dependencies.logDetachedWarning('Failed to release detached window', { windowId, error: runtimeError });
    }
};

const listOpenWindows = (state: MetadataStoreState, dependencies: RuntimeEnvLogger): OpenWindowInfo[] => {
    const results: OpenWindowInfo[] = [];
    for (const [windowId, windowData] of state.openWindows.entries()) {
        if (!isObject(windowData)) {
            dependencies.logDetachedWarning('Detached window record is invalid during enumeration', { windowId });
            continue;
        }
        if (windowData.window?.closed) {
            continue;
        }
        if (!isValidRuntimeString(windowData.pageId)) {
            dependencies.logDetachedWarning('Detached window record must include a pageId', { windowId });
            continue;
        }
        if (!isNumber(windowData.openedAt) || !Number.isFinite(windowData.openedAt)) {
            dependencies.logDetachedWarning('Detached window record must include an openedAt timestamp', { windowId });
            continue;
        }
        results.push({ windowId, pageId: windowData.pageId, openedAt: windowData.openedAt });
    }
    return results;
};

const closeAllOpenWindows = (state: MetadataStoreState, dependencies: ReleaseDependencies): void => {
    for (const [windowId, windowData] of state.openWindows.entries()) {
        if (!isObject(windowData)) {
            dependencies.logDetachedWarning('Detached window record is invalid during closeAll', { windowId });
            continue;
        }
        if (windowData.window && !windowData.window.closed) {
            try {
                windowData.window.close();
            } catch (error) {
                const runtimeError = ensureError(error);
                dependencies.logDetachedWarning('Detached window close failed during closeAll', {
                    windowId,
                    error: runtimeError
                });
            }
        }
        safeReleaseWindowRecord(state, windowId, dependencies);
    }
};

const clearWindowMonitor = (monitorId: number): void => {
    getWindow().clearInterval(monitorId);
};

export { clearWindowMonitor, closeAllOpenWindows, collectDetachedContext, getWindowRecordForAction, listOpenWindows, prepareDetachedContextForPage, releaseWindowRecord, safeReleaseWindowRecord, storeWindowMetadata, takePendingWindowMetadata };
