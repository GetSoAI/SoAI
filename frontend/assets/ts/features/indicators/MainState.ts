/* SoAI - Indicators feature main state [frontend/assets/ts/features/indicators/MainState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { hasFunctionProperties, isFunction, isObject } from '@core/typeGuards.ts';
import { createMainStateIndicatorUI, updateMainStateIndicatorUI } from '@features/indicators/mainStateIndicatorUI.ts';

const MAIN_STATE_MODULE_ID = 'features.indicators.MainState';

type StateType = 'unknown' | 'healthy' | 'degraded' | 'error' | string;

interface StatusMonitor {
    subscribe(callback: (state: StateType) => void): () => void;
    getCurrentState(): StateType | null;
    isConnectionHealthy?(): boolean;
    initialize?(): Promise<void>;
}

interface ErrorHandlerInterface {
    debug: (context: string, message: string, error?: TelemetryValue) => void;
    info: (context: string, message: string, error?: TelemetryValue) => void;
    warn: (context: string, message: string, error?: TelemetryValue) => void;
    error: (context: string, message: string, error?: TelemetryValue) => void;
}

interface MainStateIndicatorComponentOptions {
    errorHandlerRef?: ErrorHandlerInterface;
    statusMonitorResolver?: () => StatusMonitor;
}

const isStatusMonitor = <T>(value: T): value is T & StatusMonitor => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperties(value, ['subscribe', 'getCurrentState']);
};

const resolveMainStatusMonitor = (): StatusMonitor => {
    const candidate = resolveKernelService('core.mainStatusMonitor');
    if (isStatusMonitor(candidate)) {
        return candidate;
    }
    throw new Error('core.mainStatusMonitor is not a StatusMonitor');
};

class MainStateIndicatorComponent {
    element: HTMLElement | null;
    statusSubscription: (() => void) | null;
    currentState: StateType;
    connectionInterrupted: boolean;
    isCollapsed: boolean;
    initializationTask: Promise<void> | null;
    statusMonitor: StatusMonitor | null;
    errorHandler: ErrorHandlerInterface;
    statusMonitorResolver: () => StatusMonitor;

    constructor({ errorHandlerRef = errorHandler, statusMonitorResolver = resolveMainStatusMonitor }: MainStateIndicatorComponentOptions = {}) {
        this.element = null;
        this.statusSubscription = null;
        this.currentState = 'unknown';
        this.connectionInterrupted = false;
        this.isCollapsed = false;
        this.initializationTask = null;
        this.statusMonitor = null;
        this.errorHandler = errorHandlerRef;
        this.statusMonitorResolver = statusMonitorResolver;
    }

    async initialize(): Promise<HTMLElement | null> {
        if (!this.initializationTask) {
            this.initializationTask = this.bootstrap();
        }
        await this.initializationTask;
        return this.element;
    }

    async bootstrap(): Promise<void> {
        this.statusMonitor = this.statusMonitorResolver();
        this.validateDependencies();
        this.element = this.createElement();
        await this.setupStatusMonitoring();
        if (this.isCollapsed) {
            this.applyCollapsedState(true);
        }
    }

    validateDependencies(): void {
        if (!this.statusMonitor) {
            throw new Error('MainStatusMonitor not initialized');
        }
        if (!isFunction(this.statusMonitor.subscribe)) {
            throw new Error('MainStatusMonitor.subscribe is not a function');
        }
        if (!this.errorHandler) {
            throw new Error('ErrorHandler not available');
        }
    }

    createElement(): HTMLElement {
        const indicator = createMainStateIndicatorUI(this.connectionInterrupted ? 'reconnecting' : this.currentState);
        indicator.id = 'main-state-indicator';
        return indicator;
    }

    async setupStatusMonitoring(): Promise<void> {
        if (isFunction(this.statusSubscription)) {
            this.statusSubscription();
            this.statusSubscription = null;
        }
        const monitor = this.statusMonitor;
        if (!monitor) {
            throw new Error('MainStatusMonitor not initialized');
        }
        const currentState = monitor.getCurrentState();
        if (currentState) {
            this.updateDisplay(currentState);
        }
        this.statusSubscription = monitor.subscribe((state) => this.updateDisplay(state));
        if (isFunction(monitor.isConnectionHealthy) && !monitor.isConnectionHealthy()) {
            if (isFunction(monitor.initialize)) {
                void monitor.initialize().catch((error) => {
                    this.errorHandler.warn(MAIN_STATE_MODULE_ID, 'Main status monitor initialization failed', error);
                });
            }
        }
    }

    updateDisplay(state: StateType): void {
        this.currentState = state;
        if (!this.element || this.connectionInterrupted) return;
        updateMainStateIndicatorUI(this.element, this.currentState);
    }

    setConnectionInterrupted(interrupted: boolean): void {
        if (this.connectionInterrupted === interrupted) return;
        this.connectionInterrupted = interrupted;
        if (!this.element) return;
        updateMainStateIndicatorUI(this.element, interrupted ? 'reconnecting' : this.currentState);
    }

    setCollapsed(collapsed: boolean): void {
        this.isCollapsed = collapsed;
        this.applyCollapsedState(collapsed);
    }

    applyCollapsedState(collapsed: boolean): void {
        if (!this.element) return;
        this.element.setAttribute('aria-expanded', String(!collapsed));
    }

    getElement(): HTMLElement | null {
        return this.element;
    }

    getCurrentState(): StateType {
        return this.currentState;
    }

    destroy(): void {
        this.statusSubscription?.();
        this.statusSubscription = null;
        this.element?.remove();
        this.element = null;
        this.initializationTask = null;
        this.statusMonitor = null;
        this.connectionInterrupted = false;
    }
}
export { MainStateIndicatorComponent };
export type { StateType, StatusMonitor, ErrorHandlerInterface, MainStateIndicatorComponentOptions };
