/* SoAI - Overlays feature restart service [frontend/assets/ts/features/overlays/restart/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LifecycleModel } from '@core/LifecycleModel.ts';
import { startPollingLoop, type PollingLoopHandle } from '@core/concurrency/pollingLoop.ts';
import { requireDocument } from '@core/environment/public.ts';
import { getMaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createKernelResolver } from '@core/runtime/runtimeContext.ts';
import { resolveRestartApi, resolveRestartDom } from '@features/overlays/restart/adapters.ts';
import { DEFAULT_MAX_RETRIES, REBOOT_MAX_RETRIES, shouldPersistRestartOperation, shouldPollForRestartOperation } from '@features/overlays/restart/constants.ts';
import { restoreRestartOverlaySession } from '@features/overlays/restart/effects.ts';
import { awaitRestartDomReady, checkRestartBackendStatus, handleRestartBackendOnline, handleRestartMaxRetriesReached } from '@features/overlays/restart/events.ts';
import { hideRestartPresentation, showRestartPresentation } from '@features/overlays/restart/presentation.ts';
import { createRestartSessionRepository } from '@features/overlays/restart/sessionRepository.ts';
import { RestartTransitionTracker } from '@features/overlays/restart/transitionTracker.ts';
import type { ApiInterface, DomInterface, OperationType, OverlayElements, RestartOperationState, RestartOverlayShowOptions, RestartSessionRepository } from '@features/overlays/restart/types.ts';

type RestartKernelResolver = ReturnType<typeof createKernelResolver>;

class RestartOverlay extends LifecycleModel {
    #api: ApiInterface | null = null;
    #dom: DomInterface | null = null;
    #resolver: RestartKernelResolver | null = null;
    isVisible: boolean;
    currentType: OperationType | null;
    pollingLoop: PollingLoopHandle | null;
    maxRetries: number;
    currentRetry: number;
    successTimer: number | null;
    elements: OverlayElements;
    maintenanceToken: symbol | null;
    readonly transitionTracker: RestartTransitionTracker;
    readonly sessionRepository: RestartSessionRepository;
    constructor(sessionRepository: RestartSessionRepository = createRestartSessionRepository()) {
        super();
        this.sessionRepository = sessionRepository;
        this.isVisible = false;
        this.currentType = null;
        this.pollingLoop = null;
        this.maxRetries = DEFAULT_MAX_RETRIES;
        this.currentRetry = 0;
        this.successTimer = null;
        this.elements = {
            overlay: null,
            message: null,
            description: null,
            statusIcon: null
        };
        this.#resolver = createKernelResolver();
        this.maintenanceToken = null;
        this.transitionTracker = new RestartTransitionTracker({
            onInterrupted: () => this.#saveSession(),
            onRecoveredConnection: () => this.#checkRecoveredBackend()
        });
    }

    resolveService(name: string): ReturnType<RestartKernelResolver> {
        const resolver = this.#resolver ?? (this.#resolver = createKernelResolver());
        return resolver(name);
    }

    get api(): ApiInterface {
        this.#api = resolveRestartApi(this.#api, (name: string) => this.resolveService(name));
        return this.#api;
    }

    get dom(): DomInterface {
        this.#dom = resolveRestartDom(this.#dom, (name: string) => this.resolveService(name));
        return this.#dom;
    }

    async initialize(): Promise<void> {
        if (this.isInitialized || this.isDestroyed) {
            if (!this.isDestroyed) {
                await this.destroy();
            }
            this.resetLifecycleState();
        }
        await this.initializeLifecycle();
    }

    override async onInitialize(): Promise<void> {
        await awaitRestartDomReady({
            addDomReadyListener: (listener: () => void): (() => void) | null => {
                return this.resources?.addEventListener(requireDocument(), 'DOMContentLoaded', listener, { once: true }) ?? null;
            }
        });
        this.#cacheElements();
        this.checkCachedState();
    }

    #cacheElements(): void {
        this.elements = {
            overlay: this.dom.querySafe('#restart-overlay'),
            message: this.dom.querySafe('#restart-message'),
            description: this.dom.querySafe('#restart-description'),
            statusIcon: this.dom.querySafe('#restart-status-icon')
        };
    }

    override async onDestroy(): Promise<void> {
        this.stopPolling();
        if (this.successTimer) {
            this.lifecycleResources.clearTimer(this.successTimer);
            this.successTimer = null;
        }

        this.isVisible = false;
        this.currentType = null;
        this.transitionTracker.stop();
        this.#releaseMaintenance();
    }

    show(type: OperationType, options: RestartOverlayShowOptions = {}): void {
        const shouldPersist = shouldPersistRestartOperation(type);
        if (this.successTimer) {
            this.lifecycleResources.clearTimer(this.successTimer);
            this.successTimer = null;
        }
        this.stopPolling();
        const observeTransition = options.observeTransition === true;
        if (shouldPersist) this.#activateMaintenance(type, observeTransition);
        this.currentType = type;
        this.isVisible = true;
        this.currentRetry = 0;
        this.maxRetries = type === 'system-reboot' ? REBOOT_MAX_RETRIES : DEFAULT_MAX_RETRIES;
        this.transitionTracker.begin(observeTransition);
        if (!shouldPersist) {
            this.sessionRepository.clear();
        }

        const presented = showRestartPresentation(this.elements, type, {
            addClassName: (element, className) => this.lifecycleDom.addClass(element, className),
            removeClassName: (element, className) => this.lifecycleDom.removeClass(element, className),
            updateHtml: (element, value) => this.lifecycleDom.updateHtml(element, value),
            updateText: (element, value) => this.lifecycleDom.updateText(element, value)
        });
        if (presented) {
            if (shouldPollForRestartOperation(type)) {
                this.startPolling();
            }

            if (shouldPersist) {
                this.#saveSession();
            }
        }
    }

    hide(): void {
        this.isVisible = false;
        this.currentType = null;
        this.transitionTracker.stop();
        this.stopPolling();
        if (this.successTimer) {
            this.lifecycleResources.clearTimer(this.successTimer);
            this.successTimer = null;
        }
        this.#releaseMaintenance();

        hideRestartPresentation(this.elements, {
            addClassName: (element, className) => this.lifecycleDom.addClass(element, className),
            removeClassName: (element, className) => this.lifecycleDom.removeClass(element, className)
        });
        this.sessionRepository.clear();
    }

    startPolling(): void {
        this.stopPolling();
        this.pollingLoop = startPollingLoop({
            label: 'RestartOverlayBackendStatus',
            intervalMs: 1000,
            initialDelayMs: 1000,
            run: async () => {
                await this.checkBackendStatus();
            }
        });
    }

    stopPolling(): void {
        if (this.pollingLoop) {
            this.pollingLoop.stop('restart-overlay-stop');
            this.pollingLoop = null;
        }
    }

    async checkBackendStatus(): Promise<void> {
        if (!this.isVisible || this.currentType === null) {
            return;
        }
        const result = await checkRestartBackendStatus({
            currentRetry: this.currentRetry,
            currentType: this.currentType,
            description: this.elements.description,
            api: this.api,
            interruptionObserved: this.transitionTracker.interruptionObserved,
            observeTransition: this.transitionTracker.observeTransition,
            updateText: (element, value) => this.lifecycleDom.updateText(element, value)
        });
        this.currentRetry = result.currentRetry;
        this.transitionTracker.restoreInterruption(result.interruptionObserved);
        this.#saveSession();
        if (result.isOnline) {
            if (this.successTimer) {
                return;
            }
            this.stopPolling();
            this.handleBackendOnline();
            return;
        }
        if (this.currentRetry >= this.maxRetries) {
            this.handleMaxRetriesReached();
        }
    }

    handleBackendOnline(): void {
        if (this.successTimer) {
            return;
        }
        this.successTimer = handleRestartBackendOnline({
            currentType: this.currentType,
            elements: this.elements,
            api: this.api,
            updateText: (element, value) => this.lifecycleDom.updateText(element, value),
            setTimer: (callback, delayMs) => this.lifecycleResources.setTimer(callback, delayMs),
            showNotification: (message, type) => this.showNotification(message, type),
            hide: () => this.hide()
        });
    }

    handleMaxRetriesReached(): void {
        const timerId = handleRestartMaxRetriesReached({
            currentRetry: this.currentRetry,
            maxRetries: this.maxRetries,
            currentType: this.currentType,
            successTimer: this.successTimer,
            elements: this.elements,
            repository: this.sessionRepository,
            updateText: (element, value) => this.lifecycleDom.updateText(element, value),
            setTimer: (callback, delayMs) => this.lifecycleResources.setTimer(callback, delayMs),
            clearTimer: (timerId) => this.lifecycleResources.clearTimer(timerId),
            addEventListener: (target, event, handler) => {
                this.lifecycleResources.addEventListener(target, event, handler);
            },
            addClassName: (target, className) => this.lifecycleDom.addClass(target, className),
            removeClassName: (target, className) => this.lifecycleDom.removeClass(target, className),
            stopPolling: () => this.stopPolling()
        });
        if (timerId) {
            this.successTimer = timerId;
        }
    }

    checkCachedState(): void {
        restoreRestartOverlaySession({
            repository: this.sessionRepository,
            showOperation: (state) => this.#restoreSession(state),
            setCurrentRetry: (retryCount) => {
                this.currentRetry = retryCount;
            }
        });
    }

    #restoreSession(state: RestartOperationState): void {
        this.show(state.type, { observeTransition: state.observeTransition });
        this.transitionTracker.restoreInterruption(state.interruptionObserved);
        this.#saveSession();
    }

    #checkRecoveredBackend(): void {
        terminateHandledPromise(this.checkBackendStatus());
    }

    #saveSession(): void {
        if (!this.isVisible || this.currentType === null || !shouldPersistRestartOperation(this.currentType)) return;
        this.sessionRepository.save({
            type: this.currentType,
            timestamp: Date.now(),
            retry: this.currentRetry,
            observeTransition: this.transitionTracker.observeTransition,
            interruptionObserved: this.transitionTracker.interruptionObserved
        });
    }

    #activateMaintenance(reason: string, observeTransition: boolean): void {
        this.#releaseMaintenance();
        this.maintenanceToken = getMaintenanceCoordinator().activate(reason, { mode: observeTransition ? 'observe' : 'hold' });
    }

    #releaseMaintenance(): void {
        if (this.maintenanceToken) {
            getMaintenanceCoordinator().deactivate(this.maintenanceToken);
            this.maintenanceToken = null;
        }
    }
}

export { RestartOverlay };
