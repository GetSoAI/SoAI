/* SoAI - Tasks feature task manager [frontend/assets/ts/features/tasks/TaskManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import { TASK_MANAGER_SERVICE_ID, type TaskLocalOperationUpdate, type TaskOperationEntry, type TaskOperationFilter, type TaskOperationListener, type TaskOperationsApi } from '@core/tasks/protocols.ts';
import { isBoolean, isFunction } from '@core/typeGuards.ts';
import { showNotification, type NotificationType } from '@core/ui/notifications/notifications.ts';
import { TaskOperationApiController } from '@features/tasks/taskmanager/TaskOperationApiController.ts';
import { TaskOperationCancellationController } from '@features/tasks/taskmanager/TaskOperationCancellationController.ts';
import { TaskManagerActions } from '@features/tasks/taskmanager/TaskManagerActions.ts';
import { bindTaskManagerInteractionBindings } from '@features/tasks/taskmanager/taskManagerInteractionBindings.ts';
import type { TaskManagerDependencies, TaskManagerElements, TaskManagerStoreApi } from '@features/tasks/taskmanager/taskManagerTypes.ts';
import { TaskManagerView } from '@features/tasks/taskmanager/TaskManagerView.ts';
import { runAsyncCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';

const TASK_PANEL_EXPANDED_STORAGE_KEY = 'header_task_panel_expanded';

class TaskManager extends LifecycleModel implements TaskOperationsApi {
    #dependencies: TaskManagerDependencies;
    #store: TaskManagerStoreApi;
    #view: TaskManagerView;
    #actions: TaskManagerActions;
    #operationCancellation: TaskOperationCancellationController;
    #operations: TaskOperationApiController;
    #elements: TaskManagerElements | null = null;
    #storeSubscription: (() => void) | null = null;
    #lifecycleGeneration = 0;

    isExpanded = false;
    constructor(dependencies: TaskManagerDependencies) {
        super({ moduleId: TASK_MANAGER_SERVICE_ID, name: 'TaskManager', type: 'component' });
        if (!dependencies) {
            throw new Error('TaskManager requires deps');
        }
        if (!dependencies.dom || !isFunction(dependencies.dom.getDocument)) {
            throw new Error('TaskManager requires dom.getDocument');
        }
        if (!dependencies.statusManager || !isFunction(dependencies.statusManager.createIndicator)) {
            throw new Error('TaskManager requires statusManager.createIndicator');
        }
        if (!dependencies.apiClient || !isFunction(dependencies.apiClient.post)) {
            throw new Error('TaskManager requires apiClient');
        }
        if (!dependencies.stream) {
            throw new Error('TaskManager requires stream owners');
        }
        if (!isFunction(dependencies.createStore)) {
            throw new Error('TaskManager requires createStore');
        }
        if (!dependencies.storage || !isFunction(dependencies.storage.get) || !isFunction(dependencies.storage.set)) {
            throw new Error('TaskManager requires storage.get and storage.set');
        }

        this.#dependencies = dependencies;
        this.#store = dependencies.createStore();
        this.#view = new TaskManagerView({ store: this.#store, statusManager: dependencies.statusManager });
        this.#operationCancellation = new TaskOperationCancellationController({
            store: this.#store,
            stream: dependencies.stream,
            showNotification: (message: string, type: NotificationType) => showNotification(message, type)
        });
        this.#actions = new TaskManagerActions({
            apiClient: dependencies.apiClient,
            stream: dependencies.stream,
            store: this.#store,
            operationCancellation: this.#operationCancellation,
            showNotification: (message: string, type: NotificationType) => showNotification(message, type),
            hidePanel: () => this.#collapse()
        });
        this.#operations = new TaskOperationApiController({ store: this.#store, cancellation: this.#operationCancellation });
    }

    async initialize(): Promise<void> {
        if (this.isInitialized) {
            await this.destroy();
        }
        if (this.isDestroyed) this.resetLifecycleState();
        await this.initializeLifecycle();
    }

    override async onInitialize(): Promise<void> {
        const lifecycleGeneration = this.#nextLifecycleGeneration();
        if (this.#elements || this.#storeSubscription) {
            await this.#releaseViewBindings();
            if (!this.#isCurrentLifecycle(lifecycleGeneration)) {
                return;
            }
        }
        this.isExpanded = this.#resolveExpandedPreference();
        this.#elements = this.#view.resolveElements();
        await this.#view.setupIcons(this.#elements);
        if (!this.#isCurrentLifecycle(lifecycleGeneration)) {
            return;
        }
        this.#view.applyLocalization(this.#elements, this.isExpanded);
        const doc = this.#dependencies.dom.getDocument();
        const win = doc.defaultView;
        if (!win) {
            throw new Error('TaskManager requires a Window');
        }
        this.lifecycleResources.addEventListener(win, 'soai:language:changed', () => {
            if (!this.#elements) {
                throw new Error('TaskManager elements not initialized');
            }
            this.#view.applyLocalization(this.#elements, this.isExpanded);
        });

        this.#setupEventListeners();
        this.#bindStore();
        await this.#store.initialize();
        if (!this.#isCurrentLifecycle(lifecycleGeneration)) {
            return;
        }
    }

    override async onDestroy(): Promise<void> {
        this.#nextLifecycleGeneration();
        this.#operationCancellation.reset();
        if (this.isExpanded) {
            if (this.#elements) {
                this.collapse();
            } else {
                this.isExpanded = false;
                this.#dependencies.storage.set(TASK_PANEL_EXPANDED_STORAGE_KEY, false);
            }
        }
        const failures: Error[] = [];
        await runAsyncCleanupStepCollectingFailure(() => this.#releaseViewBindings(), failures);
        await runAsyncCleanupStepCollectingFailure(async () => {
            await this.#store.destroy();
        }, failures);
        throwCollectedCleanupFailures(failures);
    }

    toggle(): void {
        if (this.isExpanded) {
            this.collapse();
        } else {
            this.expand();
        }
    }

    expand(): void {
        if (!this.#elements) {
            throw new Error('TaskManager elements not initialized');
        }
        this.isExpanded = true;
        this.#dependencies.storage.set(TASK_PANEL_EXPANDED_STORAGE_KEY, true);
        this.#view.setExpandedState(this.#elements, true);
        terminateHandledPromise(this.#store.reconcileOperations());
        this.renderPluginList();
    }

    collapse(): void {
        this.#collapse();
    }

    #collapse(): void {
        if (!this.#elements) {
            throw new Error('TaskManager elements not initialized');
        }
        this.isExpanded = false;
        this.#dependencies.storage.set(TASK_PANEL_EXPANDED_STORAGE_KEY, false);
        this.#view.setExpandedState(this.#elements, false);
    }

    getOperations(filter: TaskOperationFilter = {}): TaskOperationEntry[] {
        return this.#operations.getOperations(filter);
    }

    subscribeOperations(filter: TaskOperationFilter, listener: TaskOperationListener): () => void {
        return this.#operations.subscribeOperations(filter, listener);
    }

    async reconcileOperations(): Promise<void> {
        await this.#store.reconcileOperations();
    }

    async cancelOperationById(operationId: string): Promise<void> {
        await this.#operations.cancelOperationById(operationId);
    }

    getPluginKey(source: string | null | undefined): string | null {
        return this.#operations.getPluginKey(source);
    }

    upsertLocalOperation(update: TaskLocalOperationUpdate): void {
        this.#operations.upsertLocalOperation(update);
    }

    removeLocalOperation(operationId: string): void {
        this.#operations.removeLocalOperation(operationId);
    }

    async stopAllPlugins(): Promise<void> {
        if (this.isExpanded) {
            this.collapse();
        }
        await this.#actions.stopAllPlugins();
    }

    renderPluginList(): void {
        if (!this.#elements) {
            throw new Error('TaskManager elements not initialized');
        }
        this.#view.renderPluginList(this.#elements);
    }

    #setupEventListeners(): void {
        if (!this.#elements) {
            throw new Error('TaskManager elements not initialized');
        }
        const doc = this.#dependencies.dom.getDocument();
        bindTaskManagerInteractionBindings({
            host: {
                addEventListener: (target, event, handler) => this.lifecycleResources.addEventListener(target, event, handler)
            },
            elements: this.#elements,
            documentRef: doc,
            handlers: {
                toggle: () => this.toggle(),
                collapse: () => this.collapse(),
                isExpanded: () => this.isExpanded,
                stopAllPlugins: async () => await this.stopAllPlugins(),
                handleStopButtonClick: async (button) => await this.#actions.handleStopButtonClick(button)
            }
        });
    }

    #bindStore(): void {
        if (this.#storeSubscription) {
            this.#storeSubscription();
            this.#storeSubscription = null;
        }
        const unsubscribe = this.#store.subscribe(() => this.#handleStoreUpdate());
        if (!isFunction(unsubscribe)) {
            throw new Error('TaskManagerStore subscribe must return an unsubscribe function');
        }
        this.#storeSubscription = unsubscribe;
        this.#handleStoreUpdate();
    }

    #handleStoreUpdate(): void {
        if (!this.#elements) {
            throw new Error('TaskManager elements not initialized');
        }
        this.#view.updateHeader(this.#elements);
        this.#updateStopAllAvailability(this.#elements);
        if (this.isExpanded) {
            this.renderPluginList();
        }
    }

    #updateStopAllAvailability(elements: TaskManagerElements): void {
        const stopCount = this.#store.getStoppableCount();
        const cancelCount = this.#store.getCancelableOperations().length;
        const enabled = stopCount > 0 || cancelCount > 0;
        elements.stopAllButton.disabled = !enabled;
    }

    #resolveExpandedPreference(): boolean {
        const stored = this.#dependencies.storage.get(TASK_PANEL_EXPANDED_STORAGE_KEY, false);
        return isBoolean(stored) ? stored : false;
    }

    #nextLifecycleGeneration(): number {
        this.#lifecycleGeneration += 1;
        return this.#lifecycleGeneration;
    }

    #isCurrentLifecycle(lifecycleGeneration: number): boolean {
        return this.#lifecycleGeneration === lifecycleGeneration;
    }

    async #releaseViewBindings(): Promise<void> {
        if (this.#storeSubscription) {
            this.#storeSubscription();
            this.#storeSubscription = null;
        }
        this.#view.reset();
        this.#elements = null;
    }
}

export { TaskManager };
