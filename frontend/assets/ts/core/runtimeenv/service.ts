/* SoAI - Shared runtime environment service [frontend/assets/ts/core/runtimeenv/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { getLocation, getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { clearWindowMonitor, closeAllOpenWindows, listOpenWindows, safeReleaseWindowRecord } from '@core/runtimeenv/actions.ts';
import { DetachedWindowCoordinator } from '@core/runtimeenv/coordinator.ts';
import { cleanupClosedDetachedWindows, closeDetachedWindowById, focusDetachedWindowByPage, isDetachedWindowOpen, openDetachedWindow, type WindowEffectsDependencies } from '@core/runtimeenv/effects.ts';
import { handleDetachedCloseRequestEvent, handleDetachedContextEvent, handleDetachedReadyEvent, handleDetachedTeardownEvent, type WindowServiceEventDependencies } from '@core/runtimeenv/events.ts';
import { ensureEventHubAvailable, ensureStateManager } from '@core/runtimeenv/guards.ts';
import type { DetachedContext, DetachedSubscription, OpenDetachedOptions, OpenDetachedResult, OpenWindowInfo, RuntimeWindowServiceState, WindowMetadata, WindowRecord } from '@core/runtimeenv/internalContracts.ts';
import { extractCurrentWindowMetadata, isValidRuntimeString } from '@core/runtimeenv/mappers.ts';
import { LOG_TAG_DETACHED, RuntimeEnvLogger, getCurrentWindowId, getDetachedContext, getHostWindowId } from '@core/runtimeenv/serviceSupport.ts';
import { warmDetachedBundle, warmLogBundle } from '@core/runtimeenv/warmup.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
class WindowService implements RuntimeWindowServiceState {
    openWindows: Map<string, WindowRecord>;
    pendingMetadata: Map<string, WindowMetadata>;
    windowId: string;
    hostWindowId: string;
    isPrimaryWindow: boolean;
    contextDeferred: Deferred<boolean> | null;
    contextPromise: Promise<boolean> | null;
    pendingContext: DetachedContext | null;
    detachedContext: DetachedContext | null;
    detachedWarmupTask: Promise<void> | null;
    detachedSubscription: DetachedSubscription | null;
    logSnapshotTask: Promise<void> | null;
    coordinator: DetachedWindowCoordinator;
    #beforeUnloadHandler: (() => void) | null;
    constructor() {
        this.openWindows = new Map();
        this.pendingMetadata = new Map();
        this.windowId = getCurrentWindowId();
        this.hostWindowId = getHostWindowId();
        this.isPrimaryWindow = !getDetachedContext();
        this.contextDeferred = null;
        this.contextPromise = null;
        this.pendingContext = null;
        this.detachedContext = null;
        this.detachedWarmupTask = null;
        this.detachedSubscription = null;
        this.logSnapshotTask = null;
        this.coordinator = new DetachedWindowCoordinator(this.windowId);
        this.#beforeUnloadHandler = null;
        this.#registerCoordinatorHandlers();
        this.#bindUnloadListener();
        if (!this.isPrimaryWindow) {
            this.#setupDetachedListener();
        }
    }
    #logDetachedWarning(message: string, details: TelemetryValue = {}): void {
        errorHandler.warn(LOG_TAG_DETACHED, message, details);
    }
    #logDetachedError(message: string, details: TelemetryValue = {}): void {
        errorHandler.error(LOG_TAG_DETACHED, message, details);
    }
    #loggerContext(): RuntimeEnvLogger {
        return {
            logDetachedWarning: (message: string, details?: TelemetryValue): void => {
                this.#logDetachedWarning(message, details ?? {});
            }
        };
    }
    #trackAsyncTask(task: Promise<void> | undefined, contextMessage: string): void {
        if (!task || !isFunction(task.catch)) {
            return;
        }
        task.catch((error) => this.#logDetachedWarning(contextMessage, error));
    }
    #windowEffectsDependencies(): WindowEffectsDependencies {
        return {
            state: this,
            isPrimaryWindow: this.isPrimaryWindow,
            ensureStateManager,
            clearInterval: clearWindowMonitor,
            trackAsyncTask: (task: Promise<void> | undefined, contextMessage: string): void => {
                this.#trackAsyncTask(task, contextMessage);
            },
            warmDetachedBundle: (): Promise<void> => warmDetachedBundle({ state: this, isPrimaryWindow: this.isPrimaryWindow, logDetachedWarning: (message, details) => this.#logDetachedWarning(message, details ?? {}) }),
            warmLogBundle: (): Promise<void> => warmLogBundle({ state: this, isPrimaryWindow: this.isPrimaryWindow }),
            logDetachedWarning: (message: string, details?: TelemetryValue): void => {
                this.#logDetachedWarning(message, details ?? {});
            },
            logDetachedError: (message: string, details?: TelemetryValue): void => {
                this.#logDetachedError(message, details ?? {});
            }
        };
    }
    #eventDependencies(): WindowServiceEventDependencies {
        return {
            state: this,
            isPrimaryWindow: this.isPrimaryWindow,
            hostWindowId: this.hostWindowId,
            coordinator: this.coordinator,
            closeCurrentWindow: (): void => {
                getWindow().close();
            },
            ensureStateManager,
            clearInterval: clearWindowMonitor,
            trackAsyncTask: (task: Promise<void> | undefined, contextMessage: string): void => {
                this.#trackAsyncTask(task, contextMessage);
            },
            warmDetachedBundle: (): Promise<void> => warmDetachedBundle({ state: this, isPrimaryWindow: this.isPrimaryWindow, logDetachedWarning: (message, details) => this.#logDetachedWarning(message, details ?? {}) }),
            warmLogBundle: (): Promise<void> => warmLogBundle({ state: this, isPrimaryWindow: this.isPrimaryWindow }),
            logDetachedWarning: (message: string, details?: TelemetryValue): void => {
                this.#logDetachedWarning(message, details ?? {});
            }
        };
    }
    #registerCoordinatorHandlers(): void {
        this.coordinator.on('detached-context', (message) => {
            handleDetachedContextEvent(message.source, message.payload ?? null, this.#eventDependencies());
        });
        this.coordinator.on('detached-close-request', (message) => {
            handleDetachedCloseRequestEvent(message.source, message.payload ?? null, this.#eventDependencies());
        });
        if (!this.isPrimaryWindow) {
            return;
        }
        this.coordinator.on('detached-ready', (message) => {
            handleDetachedReadyEvent(message.source, message.payload, this.#eventDependencies());
        });
        this.coordinator.on('detached-teardown', (message) => {
            handleDetachedTeardownEvent(message.source, message.payload, this.#eventDependencies());
        });
    }
    #bindUnloadListener(): void {
        const handler = this.isPrimaryWindow ? () => this.closeAllWindows() : () => this.#notifyClosing();
        this.#beforeUnloadHandler = handler;
        ensureEventHubAvailable().addEventListener('beforeunload', handler, { passive: true });
    }
    #setupDetachedListener(): void {
        this.#ensureContextPromise();
        if (!this.coordinator) {
            this.#logDetachedWarning('Detached window coordinator is unavailable for detached listener setup');
            return;
        }
        this.coordinator.send('detached-ready', { windowId: this.windowId, metadata: extractCurrentWindowMetadata(getLocation().search) }, this.hostWindowId);
    }
    #ensureContextPromise(): void {
        if (this.isPrimaryWindow) {
            this.contextPromise = Promise.resolve(true);
            return;
        }
        if (this.contextPromise) {
            return;
        }
        this.contextDeferred = createDeferred<boolean>();
        this.contextPromise = this.contextDeferred.promise;
    }
    #notifyClosing(): void {
        if (this.isPrimaryWindow) {
            this.closeAllWindows();
            return;
        }
        if (!this.coordinator) {
            this.#logDetachedWarning('Detached window coordinator is unavailable during detached teardown notify');
            return;
        }
        this.coordinator.send('detached-teardown', { windowId: this.windowId }, this.hostWindowId);
    }
    #safeReleaseWindow(windowId: string): void {
        safeReleaseWindowRecord(this, windowId, {
            clearInterval: clearWindowMonitor,
            logDetachedWarning: (message: string, details?: TelemetryValue): void => {
                this.#logDetachedWarning(message, details ?? {});
            }
        });
    }
    awaitDetachedContext(options: { timeout?: number } = {}): Promise<boolean> {
        if (this.isPrimaryWindow) {
            throw new Error('Primary window cannot await detached context');
        }
        if (!isObject(options)) {
            throw new Error('Detached context options must be an object');
        }
        this.#ensureContextPromise();
        if (!this.contextPromise) {
            throw new Error('Detached context promise was not initialized');
        }
        const timeoutValue = options['timeout'];
        if (timeoutValue === undefined) {
            return this.contextPromise;
        }
        const timeout = Number(timeoutValue);
        if (!Number.isFinite(timeout) || timeout <= 0) {
            throw new Error('Detached context timeout must be a positive number');
        }
        return withTimeout(this.contextPromise, { timeoutMs: timeout, timeoutMessage: 'Detached context timeout' });
    }
    getDetachedContext(): DetachedContext | null {
        if (this.isPrimaryWindow) {
            return null;
        }
        return this.detachedContext;
    }
    getDetachedMetadata(): WindowMetadata | null {
        const context = this.getDetachedContext();
        if (!context) {
            return null;
        }
        return context.metadata;
    }
    notifyDetachedClosed(windowId: string = this.windowId): void {
        if (!isValidRuntimeString(windowId)) {
            this.#logDetachedWarning('Detached window close notification requires a windowId', { windowId });
            return;
        }
        const key = windowId.trim();
        if (this.isPrimaryWindow) {
            this.#safeReleaseWindow(key);
            return;
        }
        if (!this.coordinator) {
            this.#logDetachedWarning('Detached window coordinator is unavailable');
            return;
        }
        this.coordinator.send('detached-teardown', { windowId: key }, this.hostWindowId);
    }
    openDetached(pageId: string, options: OpenDetachedOptions = {}): OpenDetachedResult | null {
        return openDetachedWindow(pageId, options, this.#windowEffectsDependencies());
    }
    focusByPage(pageId: string): boolean {
        return focusDetachedWindowByPage(pageId, this.#windowEffectsDependencies());
    }
    closeWindow(windowId: string): boolean {
        return closeDetachedWindowById(windowId, this.#windowEffectsDependencies());
    }
    closeAllWindows(): void {
        closeAllOpenWindows(this, {
            clearInterval: clearWindowMonitor,
            logDetachedWarning: (message: string, details?: TelemetryValue): void => {
                this.#logDetachedWarning(message, details ?? {});
            }
        });
    }
    getOpenWindows(): OpenWindowInfo[] {
        cleanupClosedDetachedWindows(this.#windowEffectsDependencies());
        return listOpenWindows(this, this.#loggerContext());
    }
    isWindowOpen(windowId: string): boolean {
        return isDetachedWindowOpen(windowId, this.#windowEffectsDependencies());
    }

    destroy(): void {
        if (this.#beforeUnloadHandler) {
            ensureEventHubAvailable().removeEventListener('beforeunload', this.#beforeUnloadHandler);
            this.#beforeUnloadHandler = null;
        }
        this.closeAllWindows();
        this.openWindows.clear();
        this.pendingMetadata.clear();
        this.contextDeferred = null;
        this.contextPromise = null;
        this.pendingContext = null;
        this.detachedContext = null;
        this.detachedWarmupTask = null;
        this.detachedSubscription = null;
        this.logSnapshotTask = null;
        this.coordinator.destroy();
    }
}
let windowServiceInstance: WindowService | null = null;
const getWindowService = (): WindowService => {
    if (!windowServiceInstance) {
        windowServiceInstance = new WindowService();
    }
    return windowServiceInstance;
};
const resetWindowService = (): void => {
    if (!windowServiceInstance) {
        return;
    }
    windowServiceInstance.destroy();
    windowServiceInstance = null;
};
export { WindowService, getWindowService, resetWindowService };
export type { OpenDetachedOptions, OpenDetachedResult, OpenWindowInfo, WindowMetadata };
