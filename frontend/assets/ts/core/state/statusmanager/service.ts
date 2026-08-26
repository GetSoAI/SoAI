/* SoAI - Shared state status manager service [frontend/assets/ts/core/state/statusmanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { StatusDefinition } from '@core/state/constants.ts';
import { buildStatusSnapshot, initializeState, isActive, isError, isTransitioning, listColors, listStatuses, normalizeStatus, resolveCollectionBadgeClass, resolveCollectionStatusClass, resolveStatusColor, resolveStatusDefinition, resolveStatusDescription, resetStatusState } from '@core/state/statusmanager/actions.ts';
import type { AuthService, StatusManagerOptions } from '@core/state/statusmanager/contracts.ts';
import { createStatusStreamMonitor, initializeAuthIntegration, refreshDefinitionsFromBackend } from '@core/state/statusmanager/effects.ts';
import type { StreamMonitorResult, StatusManagerState } from '@core/state/statusmanager/internalContracts.ts';
import type { StatusInput } from '@core/state/statusTypes.ts';
import { isElementNode, isObject, isString } from '@core/typeGuards.ts';
import { serializeElementToHtml } from '@core/dom/html.ts';

type IndicatorSize = 'small' | 'medium' | 'large';

const STATUS_INDICATOR_CLASS = 'status-indicator';
const STATUS_INDICATOR_ACTIVE_CLASS = 'is-active';
const STATUS_INDICATOR_TRANSITIONING_CLASS = 'is-transitioning';
const STATUS_BADGE_CLASS = 'ui-status-badge';
const STATUS_PREFIX = 'status-';

const INDICATOR_MUTABLE_CLASSES = new Set([STATUS_INDICATOR_CLASS, STATUS_INDICATOR_ACTIVE_CLASS, STATUS_INDICATOR_TRANSITIONING_CLASS]);

const ensureOptions = (options: StatusManagerOptions): StatusManagerOptions => {
    if (!isObject(options)) {
        throw new Error('StatusManager requires options');
    }
    if (!options.dom) {
        throw new Error('StatusManager requires dom service');
    }
    if (!options.errorHandler) {
        throw new Error('StatusManager requires error handler');
    }
    if (!isString(options.statusStreamId) || !options.statusStreamId.trim()) {
        throw new Error('StatusManager requires a non-empty statusStreamId');
    }
    if (!options.apiClientProvider) {
        throw new Error('StatusManager requires apiClientProvider');
    }
    if (!options.authServiceProvider) {
        throw new Error('StatusManager requires authServiceProvider');
    }
    return options;
};

class StatusManager {
    readonly #options: StatusManagerOptions;
    readonly #state: StatusManagerState;
    #auth: AuthService | null = null;
    readonly #authSubscriptions = new ResourceTracker();
    #streamMonitor: StreamMonitorResult | null = null;
    #definitionsPromise: Promise<StatusManagerState['definitions']> | null = null;
    #initializePromise: Promise<void> | null = null;
    #destroyed: boolean = false;
    #initialized: boolean = false;

    constructor(options: StatusManagerOptions) {
        this.#options = ensureOptions(options);
        this.#state = initializeState();
    }

    initialize(): Promise<void> {
        if (this.#initialized) {
            return Promise.resolve();
        }
        if (this.#initializePromise) {
            return this.#initializePromise;
        }
        const task = this.#initialize().finally(() => {
            this.#initializePromise = null;
        });
        this.#initializePromise = task;
        return task;
    }

    async #initialize(): Promise<void> {
        if (this.#initialized || this.#destroyed) {
            return;
        }

        const integration = await initializeAuthIntegration({
            authServiceProvider: this.#options.authServiceProvider,
            stateErrorHandler: this.#options.errorHandler,
            resources: this.#authSubscriptions,
            onLogin: () => {
                terminateHandledPromise(this.#refreshDefinitions());
            },
            onLogout: () => {
                resetStatusState(this.#state);
            }
        });

        if (this.#destroyed) {
            this.#authSubscriptions.cleanup();
            return;
        }

        this.#auth = integration.auth;
        this.#streamMonitor = createStatusStreamMonitor({
            streamManagerProvider: this.#options.streamManagerProvider,
            statusStreamId: this.#options.statusStreamId,
            onStatus: (status: StatusInput) => {
                buildStatusSnapshot(this.#state, status);
            },
            onError: (module: string, message: string, runtimeError: Error) => {
                const logger = this.#options.errorHandler.error || errorHandler.error;
                if (logger) {
                    logger(module, message, runtimeError);
                }
            }
        });

        if (this.#isAuthenticated()) {
            await this.#refreshDefinitions();
        }
        this.#initialized = true;
    }

    #isAuthenticated(): boolean {
        return this.#auth?.isAuthenticated === true;
    }

    async #refreshDefinitions(): Promise<void> {
        if (this.#destroyed) {
            return;
        }
        await refreshDefinitionsFromBackend({
            state: this.#state,
            isAuthenticated: () => this.#isAuthenticated(),
            apiClientProvider: this.#options.apiClientProvider,
            getDefinitionsPromise: () => this.#definitionsPromise,
            setDefinitionsPromise: (next: Promise<StatusManagerState['definitions']> | null) => {
                this.#definitionsPromise = next;
            },
            reportError: (module: string, message: string, runtimeError: Error) => {
                const logger = this.#options.errorHandler.error || errorHandler.error;
                if (logger) {
                    logger(module, message, runtimeError);
                }
            }
        });
    }

    #statusColorClasses(): Set<string> {
        const classes = new Set<string>();
        for (const color of listColors(this.#state)) {
            classes.add(color);
            classes.add(`${STATUS_PREFIX}${color}`);
        }
        return classes;
    }

    #applyIndicatorClasses(element: Element, status: StatusInput, size: IndicatorSize): void {
        const classList = Array.from(element.classList);
        const colorClasses = this.#statusColorClasses();
        const baseClasses = new Set<string>([...INDICATOR_MUTABLE_CLASSES, ...colorClasses, 'status-led-sm']);
        const preserved = classList.filter((className) => !baseClasses.has(className));
        const statusClasses = [STATUS_INDICATOR_CLASS, resolveStatusColor(this.#state, status)];
        if (size === 'small') {
            statusClasses.push('status-led-sm');
        }
        if (isActive(this.#state, status)) {
            statusClasses.push(STATUS_INDICATOR_ACTIVE_CLASS);
        }
        if (isTransitioning(this.#state, status)) {
            statusClasses.push(STATUS_INDICATOR_TRANSITIONING_CLASS);
        }
        element.className = [...preserved, ...statusClasses].join(' ').trim();
    }

    normalizeStatus(status: StatusInput): string {
        return normalizeStatus(this.#state, status);
    }

    getDefinition(status: StatusInput): StatusDefinition {
        return resolveStatusDefinition(this.#state, status);
    }

    getColor(status: StatusInput): string {
        return resolveStatusColor(this.#state, status);
    }

    getDescription(status: StatusInput): string {
        return resolveStatusDescription(this.#state, status);
    }

    getCollectionStatusClass(status: StatusInput): string {
        return resolveCollectionStatusClass(this.#state, status);
    }

    getCollectionBadgeClass(status: StatusInput): string {
        return resolveCollectionBadgeClass(this.#state, status);
    }

    isActive(status: StatusInput): boolean {
        return isActive(this.#state, status);
    }

    isError(status: StatusInput): boolean {
        return isError(this.#state, status);
    }

    isTransitioning(status: StatusInput): boolean {
        return isTransitioning(this.#state, status);
    }

    listStatuses(): string[] {
        return listStatuses(this.#state);
    }

    listColors(): string[] {
        return listColors(this.#state);
    }

    updateIndicator(element: Element | null, status: StatusInput): void {
        if (!element || !isElementNode(element)) {
            return;
        }
        this.#applyIndicatorClasses(element, status, 'medium');
    }

    createIndicator(status: StatusInput, size: IndicatorSize = 'medium'): HTMLElement {
        const indicator = this.#options.dom.getDocument().createElement('span');
        this.#applyIndicatorClasses(indicator, status, size);
        return indicator;
    }

    renderIndicator(status: StatusInput, size: IndicatorSize = 'small'): TrustedHtml {
        return toTrustedUiHtml(serializeElementToHtml(this.createIndicator(status, size)));
    }

    createStatusBadge(status: StatusInput, description: string): HTMLElement {
        const badge = this.#options.dom.getDocument().createElement('span');
        const color = this.getColor(status);
        badge.className = `${STATUS_BADGE_CLASS} ${STATUS_PREFIX}${color} ${color}`;
        const label = description.trim() || this.getDescription(status);
        badge.textContent = label;
        return badge;
    }

    destroy(): void {
        if (this.#destroyed) {
            return;
        }
        this.#destroyed = true;
        this.#authSubscriptions.cleanup();
        this.#auth = null;
        if (this.#streamMonitor) {
            this.#streamMonitor.stop();
            this.#streamMonitor = null;
        }
        this.#definitionsPromise = null;
        this.#initializePromise = null;
    }
}

export { StatusManager };
