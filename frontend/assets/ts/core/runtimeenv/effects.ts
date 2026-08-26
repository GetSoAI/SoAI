/* SoAI - Shared runtime environment effects [frontend/assets/ts/core/runtimeenv/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { getWindowOpen } from '@core/environment/public.ts';
import { encodeSegment } from '@core/identifiers.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { collectDetachedContext, getWindowRecordForAction, prepareDetachedContextForPage, safeReleaseWindowRecord, storeWindowMetadata } from '@core/runtimeenv/actions.ts';
import type { DetachedWindowCoordinator } from '@core/runtimeenv/coordinator.ts';
import type { OpenDetachedOptions, OpenDetachedResult, StateManagerInterface, WindowMetadata, WindowRecord } from '@core/runtimeenv/internalContracts.ts';
import { isValidRuntimeString, sanitizeDetachedParameters, sanitizeDetachedWindowUrl, serializeDetachedContext, trimRuntimeString } from '@core/runtimeenv/mappers.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface RuntimeEnvLogger {
    logDetachedWarning: (message: string, details?: TelemetryValue) => void;
    logDetachedError: (message: string, details?: TelemetryValue) => void;
}

interface WindowEffectsState {
    openWindows: Map<string, WindowRecord>;
    pendingMetadata: Map<string, WindowMetadata>;
    windowId: string;
    coordinator: DetachedWindowCoordinator | null;
}

interface WindowEffectsDependencies extends RuntimeEnvLogger {
    state: WindowEffectsState;
    isPrimaryWindow: boolean;
    trackAsyncTask: (task: Promise<void> | undefined, contextMessage: string) => void;
    warmDetachedBundle: () => Promise<void>;
    warmLogBundle: () => Promise<void>;
    ensureStateManager: () => StateManagerInterface;
    clearInterval: (id: number) => void;
}

const SUPPORTED_DETACHED_PAGES: readonly string[] = Object.freeze(['chat', 'logs', 'terminal', 'hardware']);

const isSupportedDetachedPage = (pageId: string): boolean => SUPPORTED_DETACHED_PAGES.includes(pageId);

const createReleaseDependencies = (dependencies: WindowEffectsDependencies): { clearInterval: (id: number) => void; logDetachedWarning: RuntimeEnvLogger['logDetachedWarning'] } => ({
    clearInterval: dependencies.clearInterval,
    logDetachedWarning: dependencies.logDetachedWarning
});

const openDetachedWindow = (pageId: string, options: OpenDetachedOptions, dependencies: WindowEffectsDependencies): OpenDetachedResult | null => {
    if (!isValidRuntimeString(pageId)) {
        throw new Error('Detached windows require a pageId');
    }
    if (options === null || options === undefined || typeof options !== 'object') {
        throw new Error('Detached window options must be an object');
    }
    if (!dependencies.isPrimaryWindow) {
        throw new Error('Detached windows cannot open child windows');
    }

    const title = options.title ?? pageId;
    const parameters = options.parameters ?? {};
    if (!isValidRuntimeString(title)) {
        throw new Error('Detached window title must be a non-empty string');
    }

    const trimmedPageId = trimRuntimeString(pageId);
    if (!isSupportedDetachedPage(trimmedPageId)) {
        throw new Error(`Page "${trimmedPageId}" is not available in detached mode. Supported: ${SUPPORTED_DETACHED_PAGES.join(', ')}`);
    }

    const windowId = `${trimmedPageId}_${windowIdentity.createDetachedIdentity()}`;
    const metadata: WindowMetadata = {
        pageId: trimmedPageId,
        parameters: sanitizeDetachedParameters(parameters, dependencies)
    };
    const url = `detached.html?page=${encodeSegment(trimmedPageId)}` + `&windowId=${encodeSegment(windowId)}` + `&hostId=${encodeSegment(dependencies.state.windowId)}`;
    const sanitizedUrl = sanitizeDetachedWindowUrl(url, dependencies);

    prepareDetachedContextForPage(metadata.pageId, {
        logDetachedWarning: dependencies.logDetachedWarning,
        trackAsyncTask: dependencies.trackAsyncTask,
        warmLogBundle: dependencies.warmLogBundle
    });
    dependencies.trackAsyncTask(dependencies.warmDetachedBundle(), 'Detached bundle warmup failed');

    storeWindowMetadata(dependencies.state, windowId, metadata, dependencies);
    let openedWindow: Window | null = null;
    try {
        openedWindow = getWindowOpen()(sanitizedUrl, '_blank', 'noopener,noreferrer');
    } catch (error) {
        dependencies.state.pendingMetadata.delete(windowId);
        const runtimeError = ensureError(error);
        dependencies.logDetachedError('Detached window open failed', { url: sanitizedUrl, windowId, error: runtimeError });
        throw runtimeError;
    }

    const record: WindowRecord = {
        window: openedWindow,
        pageId: metadata.pageId,
        openedAt: Date.now(),
        monitorId: null,
        metadata
    };
    dependencies.state.openWindows.set(windowId, record);

    if (!dependencies.state.coordinator) {
        dependencies.logDetachedWarning('Detached window coordinator is unavailable for register event', { windowId });
    } else {
        dependencies.state.coordinator.send('detached-register', { windowId, metadata, title: trimRuntimeString(title) }, dependencies.state.windowId);
    }

    const context = collectDetachedContext(windowId, metadata, {
        ensureStateManager: dependencies.ensureStateManager,
        logDetachedWarning: dependencies.logDetachedWarning
    });
    if (context && dependencies.state.coordinator) {
        dependencies.state.coordinator.send('detached-context', serializeDetachedContext(context), windowId);
    }

    if (openedWindow && isFunction(openedWindow.focus)) {
        openedWindow.focus();
    } else if (openedWindow) {
        dependencies.logDetachedWarning('Detached window handle must expose focus', { windowId });
    }

    return {
        windowId,
        window: openedWindow,
        close: (): boolean => {
            return closeDetachedWindowById(windowId, dependencies);
        }
    };
};

const focusDetachedWindowByPage = (pageId: string, dependencies: WindowEffectsDependencies): boolean => {
    if (!isValidRuntimeString(pageId)) {
        dependencies.logDetachedWarning('Detached focus requires a pageId', { pageId });
        return false;
    }
    const targetPageId = trimRuntimeString(pageId);
    const releaseDependencies = createReleaseDependencies(dependencies);
    for (const [windowId, entry] of dependencies.state.openWindows.entries()) {
        if (!isObject(entry)) {
            dependencies.logDetachedWarning('Detached window record is invalid during focus', { windowId });
            continue;
        }
        if (!entry.window) {
            continue;
        }
        if (entry.window.closed) {
            safeReleaseWindowRecord(dependencies.state, windowId, releaseDependencies);
            continue;
        }
        if (entry.pageId !== targetPageId) {
            continue;
        }
        if (!isFunction(entry.window.focus)) {
            dependencies.logDetachedWarning('Detached window handle must expose focus', { windowId });
            return false;
        }
        entry.window.focus();
        return true;
    }
    return false;
};

const closeDetachedWindowById = (windowId: string, dependencies: WindowEffectsDependencies): boolean => {
    const result = getWindowRecordForAction(dependencies.state, windowId, 'Detached window close', dependencies, {
        requireHandle: false
    });
    if (!result) {
        return false;
    }
    const { key, record } = result;
    if (!record.window) {
        if (dependencies.state.coordinator) {
            dependencies.state.coordinator.send('detached-close-request', { windowId: key }, key);
        } else {
            dependencies.logDetachedWarning('Detached window coordinator is unavailable for close request', { windowId: key });
        }
        safeReleaseWindowRecord(dependencies.state, key, createReleaseDependencies(dependencies));
        return true;
    }
    if (record.window.closed) {
        safeReleaseWindowRecord(dependencies.state, key, createReleaseDependencies(dependencies));
        dependencies.logDetachedWarning('Detached window is already closed', { windowId: key });
        return false;
    }
    try {
        record.window.close();
    } catch (error) {
        const runtimeError = ensureError(error);
        dependencies.logDetachedWarning('Detached window close failed', { windowId: key, error: runtimeError });
        throw ensureError(error);
    }
    safeReleaseWindowRecord(dependencies.state, key, createReleaseDependencies(dependencies));
    return true;
};

const cleanupClosedDetachedWindows = (dependencies: WindowEffectsDependencies): void => {
    const releaseDependencies = createReleaseDependencies(dependencies);
    for (const [windowId, entry] of dependencies.state.openWindows.entries()) {
        if (isObject(entry) && entry.window && entry.window.closed) {
            safeReleaseWindowRecord(dependencies.state, windowId, releaseDependencies);
        }
    }
};

const isDetachedWindowOpen = (windowId: string, dependencies: WindowEffectsDependencies): boolean => {
    const result = getWindowRecordForAction(dependencies.state, windowId, 'Detached window query', dependencies, {
        requireHandle: false
    });
    if (!result) {
        return false;
    }
    return result.record.window ? result.record.window.closed === false : true;
};

export { cleanupClosedDetachedWindows, closeDetachedWindowById, focusDetachedWindowByPage, isDetachedWindowOpen, openDetachedWindow };
export type { WindowEffectsDependencies, WindowEffectsState };
