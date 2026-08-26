/* SoAI - Frontend lifecycle orchestration model [frontend/assets/ts/core/LifecycleModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { coerceErrorMessage, ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { LifecycleDomAccess } from '@core/lifecyclemodel/LifecycleDomAccess.ts';
import { LifecycleResources } from '@core/lifecyclemodel/LifecycleResources.ts';
import { LifecycleStreamSession } from '@core/lifecyclemodel/LifecycleStreamSession.ts';
import { LifecycleCancellationError, isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import type { EnsureStreamResourcesOptions, HandleErrorOptions, LifecycleModelMeta, LifecycleState, NotificationService, ResourceSnapshot, StreamRuntimeOwners, TimerOptions } from '@core/lifecyclemodel/types.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import { PageContext } from '@core/pagecontext/public.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

const LIFECYCLE_MODEL_TAG = 'LifecycleModel';

class LifecycleModel {
    readonly lifecycleResources: LifecycleResources;
    readonly lifecycleStream: LifecycleStreamSession;
    #lifecycleDom: LifecycleDomAccess | null = null;
    #meta: LifecycleModelMeta;
    #pageContext: PageContext | null;
    #notifications: NotificationService | null = null;
    #state: LifecycleState = { initialized: false, destroyed: false, cleanupPerformed: false };
    #destroying = false;
    #destruction: Promise<boolean> | null = null;
    #cleanupTask: Promise<void> | null = null;
    #initialization: Promise<boolean> | null = null;
    #generation = 0;
    #pageId: string | undefined;
    name?: string;

    constructor(meta: LifecycleModelMeta = {}) {
        this.#meta = meta;
        this.#pageContext = meta.pageContext ?? null;
        this.lifecycleResources = new LifecycleResources();
        this.lifecycleStream = new LifecycleStreamSession(this.lifecycleResources);
    }

    get lifecycleDom(): LifecycleDomAccess {
        this.#lifecycleDom ??= new LifecycleDomAccess(
            () => this.getDomContext(),
            () => this.name
        );
        return this.#lifecycleDom;
    }

    get resources(): ResourceTracker {
        return this.lifecycleResources.tracker;
    }

    get pageId(): string | undefined {
        return this.#pageId;
    }

    set pageId(value: string | undefined) {
        this.#pageId = value;
    }

    get isInitialized(): boolean {
        return this.#state.initialized;
    }

    set isInitialized(value: boolean) {
        this.#state.initialized = value === true;
    }

    get isDestroyed(): boolean {
        return this.#state.destroyed;
    }

    set isDestroyed(value: boolean) {
        this.#state.destroyed = value === true;
    }

    get pageContext(): PageContext {
        this.#pageContext ??= new PageContext({ pageId: this.getLifecycleIdentifier() });
        return this.#pageContext;
    }

    set pageContext(value: PageContext | null) {
        this.#pageContext = value;
        this.#notifications = null;
    }

    get notifications(): NotificationService {
        if (this.#notifications) return this.#notifications;
        this.#notifications = this.pageContext.notifications;
        return this.#notifications;
    }

    getLifecycleIdentifier(): string {
        return (isString(this.#meta.moduleId) && this.#meta.moduleId) || (isString(this.#meta.name) && this.#meta.name) || this.constructor.name || LIFECYCLE_MODEL_TAG;
    }

    async initializeLifecycle(...inputArguments: (JsonValue | null)[]): Promise<boolean> {
        if (this.#destroying) throw new LifecycleCancellationError(`${this.constructor.name} initialization rejected during destruction`, 'lifecycle-model-destroying');
        if (this.#cleanupTask) throw new LifecycleCancellationError(`${this.constructor.name} initialization rejected during cleanup`, 'lifecycle-model-cleanup');
        if (this.#initialization) return this.#initialization;
        if (this.isInitialized) {
            errorHandler.warn(LIFECYCLE_MODEL_TAG, `${this.constructor.name} already initialized`);
            return false;
        }
        if (this.isDestroyed) throw new Error(`Cannot initialize destroyed entity ${this.constructor.name}.`);
        const generation = this.#generation;
        const initialization = this.#runInitialization(inputArguments, generation);
        this.#initialization = initialization;
        try {
            return await initialization;
        } finally {
            this.#initialization = null;
        }
    }

    async #runInitialization(inputArguments: (JsonValue | null)[], generation: number): Promise<boolean> {
        try {
            await this.beforeInitialize(...inputArguments);
            this.#requireActiveInitialization(generation);
            await this.onInitialize(...inputArguments);
            this.#requireActiveInitialization(generation);
            await this.afterInitialize(...inputArguments);
            this.#requireActiveInitialization(generation);
            this.isInitialized = true;
            this.#state.cleanupPerformed = false;
            return true;
        } catch (error) {
            if (!this.#destroying) {
                await this.#rollbackInitialization(inputArguments);
            }
            throw error;
        }
    }

    async #rollbackInitialization(inputArguments: (JsonValue | null)[]): Promise<void> {
        try {
            await this.onDestroy(...inputArguments);
        } catch (error) {
            errorHandler.error(LIFECYCLE_MODEL_TAG, `${this.constructor.name} initialization rollback hook failed`, ensureError(error));
        }
        try {
            await this.cleanup();
        } catch (error) {
            errorHandler.error(LIFECYCLE_MODEL_TAG, `${this.constructor.name} initialization rollback cleanup failed`, ensureError(error));
        }
        try {
            this.lifecycleStream.reset();
        } catch (error) {
            errorHandler.error(LIFECYCLE_MODEL_TAG, `${this.constructor.name} initialization rollback stream reset failed`, ensureError(error));
        }
        this.isInitialized = false;
        this.isDestroyed = true;
    }

    async destroy(...inputArguments: (JsonValue | null)[]): Promise<boolean> {
        if (this.isDestroyed) return false;
        if (this.#destruction) {
            await this.#destruction;
            return false;
        }
        const destruction = this.#runDestruction(inputArguments);
        this.#destruction = destruction;
        try {
            return await destruction;
        } finally {
            this.#destruction = null;
        }
    }

    async #runDestruction(inputArguments: (JsonValue | null)[]): Promise<boolean> {
        this.#destroying = true;
        this.#generation += 1;
        try {
            if (this.#cleanupTask) await this.#cleanupTask;
            const initialization = this.#initialization;
            if (initialization) {
                try {
                    await initialization;
                } catch (error) {
                    if (!isLifecycleCancellationError(error)) {
                        errorHandler.error(LIFECYCLE_MODEL_TAG, `${this.constructor.name} initialization failed before destruction`, ensureError(error));
                    }
                }
            }
            if (this.isDestroyed) return false;
            try {
                await this.beforeDestroy(...inputArguments);
                await this.onDestroy(...inputArguments);
            } catch (error) {
                errorHandler.error(LIFECYCLE_MODEL_TAG, `${this.constructor.name} destroy hooks failed`, ensureError(error));
            }
            await this.cleanup();
            this.lifecycleStream.reset();
            this.isDestroyed = true;
            this.isInitialized = false;
            return true;
        } finally {
            this.#destroying = false;
        }
    }

    async cleanup(): Promise<boolean> {
        if (this.#state.cleanupPerformed) return false;
        if (this.#cleanupTask) {
            await this.#cleanupTask;
            return false;
        }
        const cleanupTask = this.cleanupResources();
        this.#cleanupTask = cleanupTask;
        try {
            await cleanupTask;
            this.#state.cleanupPerformed = true;
            return true;
        } finally {
            this.#cleanupTask = null;
        }
    }

    async cleanupResources(): Promise<void> {
        await this.lifecycleResources.cleanup();
        this.lifecycleDom.reset();
    }

    resetLifecycleState(): void {
        if (this.#destroying) throw new Error(`Cannot reset ${this.constructor.name} while destruction is active`);
        if (this.#initialization) throw new Error(`Cannot reset ${this.constructor.name} while initialization is active`);
        if (this.#cleanupTask) throw new Error(`Cannot reset ${this.constructor.name} while cleanup is active`);
        this.#generation += 1;
        this.#state = { initialized: false, destroyed: false, cleanupPerformed: false };
    }

    #requireActiveInitialization(generation: number): void {
        if (generation !== this.#generation || this.#destroying || this.isDestroyed) {
            throw new LifecycleCancellationError(`${this.constructor.name} initialization cancelled during lifecycle transition`, 'lifecycle-model-initialization');
        }
    }

    getRequiredResources(): string[] {
        return [];
    }

    async ensureDeclaredResources(options: EnsureStreamResourcesOptions = {}): Promise<StreamRuntimeOwners | null> {
        return this.lifecycleStream.ensureDeclaredResources(this.getLifecycleIdentifier(), this.getRequiredResources(), options);
    }

    async ensureStreamResources(resourceNames: string | string[], options?: EnsureStreamResourcesOptions): Promise<StreamRuntimeOwners> {
        return this.lifecycleStream.ensureResources(resourceNames, options);
    }

    getDomContext(): Element | Document | null {
        return null;
    }

    showNotification(message: string, type: NotificationType = 'info', duration: number = 3000): void {
        this.notifications.show(message, type, duration);
    }

    showError(message: string, duration: number = 6000): void {
        this.notifications.error(message, duration);
    }

    showSuccess(message: string, duration: number = 3000): void {
        this.notifications.success(message, duration);
    }

    showWarning(message: string, duration: number = 4000): void {
        this.notifications.warning(message, duration);
    }

    showInfo(message: string, duration: number = 3000): void {
        this.notifications.info(message, duration);
    }

    handleError(error: Error, context: string = '', options: HandleErrorOptions = {}): void {
        const { notify = false, severity = 'error', rethrow = false } = options;
        const handledByNotifier = notifyHandledOperationError(error);
        const message = coerceErrorMessage(error);
        const moduleId = this.pageId || this.name || this.constructor.name;
        const formattedMessage = context ? `${context}: ${message}` : message;
        errorHandler[severity](moduleId, formattedMessage, error);
        if (notify && !handledByNotifier) {
            const notificationType: NotificationType = severity === 'warn' ? 'warning' : severity === 'error' ? 'error' : 'info';
            this.showNotification(i18n.t('common.errors.operationFailed'), notificationType);
        }
        if (rethrow) throw error;
    }

    async beforeInitialize(..._arguments: (JsonValue | null)[]): Promise<void> {}
    async onInitialize(..._arguments: (JsonValue | null)[]): Promise<void> {}
    async afterInitialize(..._arguments: (JsonValue | null)[]): Promise<void> {}
    async beforeDestroy(..._arguments: (JsonValue | null)[]): Promise<void> {}
    async onDestroy(..._arguments: (JsonValue | null)[]): Promise<void> {}
}

export { LIFECYCLE_MODEL_TAG, LifecycleModel };
export type { HandleErrorOptions, LifecycleModelMeta, NotificationService, PageContext, ResourceSnapshot, StreamRuntimeOwners, TimerOptions };
