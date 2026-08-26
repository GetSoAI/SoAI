/* SoAI - Plugins page operations controller [frontend/assets/ts/pages/plugins/controllers/operationsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiRequestBody } from '@core/api/types/request.ts';
import { MODELS_ACTION_ADD_PROVIDER, MODELS_ACTION_DOWNLOAD_MODEL } from '@core/models/pageActions.ts';
import { executeStreamItemDeletion } from '@core/routing/pages/collections/streamItemDeletion.ts';
import type { CollectionRuntime, StreamActionHandle, StreamHandleTrackerContract } from '@core/routing/pages/pagetypes/public.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isArray } from '@core/typeGuards.ts';
import { isNamedPluginRecord } from '@core/types/pluginRecordGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { PROVIDER_MODE, resolveProviderMode } from '@features/catalog/public.ts';
import type { ExecuteItemDeletionOptions } from '@pages/plugins/controllers/pluginsPageRuntimeSupport.ts';
import { createPluginDeleteStreamStarter, deletePluginWithStream } from '@pages/plugins/services/pluginsDeletePlugin.ts';
import { handleStopAllPluginsAction } from '@pages/plugins/services/pluginsStopAllAction.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { OptimisticOperation } from '@core/data/clientdatahub/types.ts';

interface PluginsOperationsPagePort extends PageDomOwnerHost, PageFeedbackOwnerHost {}

interface PluginsCollectionOperationsPort {
    deletingItems: Set<string>;
    getCollectionRuntime(): CollectionRuntime | null;
    getCatalogPlugin(identifier: string): PluginRecord | null;
    beginOptimisticOperation(operation: OptimisticOperation): void;
    sanitizeText(value: JsonValue | null | undefined): string;
    renderItems(): void;
    removeItemById(identifier: string): void;
    streams: StreamHandleTrackerContract;
}

interface PluginsOperationsControllerDependencies {
    page: PluginsOperationsPagePort;
    collection: PluginsCollectionOperationsPort;
    resolvePluginRecord(plugin: PluginRecord | string | null | undefined): PluginRecord | null;
    canExecutePluginAction(plugin: PluginRecord | string | null | undefined, options?: { notify?: boolean; allowCompatibilityOverride?: boolean }): boolean;
    isPluginIncompatible(plugin: PluginRecord): boolean;
    notifyPluginIncompatible(plugin: PluginRecord): void;
    getPluginStatus(plugin: PluginRecord): string;
    formatPluginName(name: string): string;
    navigateToModels(action: string, plugin: PluginRecord | string | null | undefined): boolean;
    startTaskAction(endpoint: string, options?: PluginOperationTaskActionOptions, runtimeOptions?: { allowDiscovery?: boolean }): Promise<StreamActionHandle>;
    isPluginStoppable(plugin: PluginRecord): boolean;
    updateStopAllButtonVisibility(): void;
    runPageTask<T>(taskKey: string, task: () => Promise<T>, options: { displayName: string; rethrow?: boolean }): Promise<T | null>;
    post(path: string, body?: ApiRequestBody): Promise<ApiResponsePayload>;
}

interface PluginOperationTaskActionOptions {
    method: string;
    body?: ApiRequestBody;
    operation?: JsonObject | null;
}

class PluginsOperationsController {
    readonly #dependencies: PluginsOperationsControllerDependencies;

    constructor(dependencies: PluginsOperationsControllerDependencies) {
        this.#dependencies = dependencies;
    }

    checkBackendInstallationSupport(plugin: PluginRecord | string | null | undefined): boolean {
        const record = this.#dependencies.resolvePluginRecord(plugin);
        return record && this.#dependencies.canExecutePluginAction(record, { notify: false }) ? (record.capabilities?.supportsBackendInstallation ?? true) !== false : false;
    }

    openDownloadModelModal(plugin: PluginRecord | string | null | undefined): void {
        const record = this.#dependencies.resolvePluginRecord(plugin);
        if (record?.name && this.#dependencies.canExecutePluginAction(record)) this.#dependencies.navigateToModels(MODELS_ACTION_DOWNLOAD_MODEL, record);
    }

    openAddProviderModal(plugin: PluginRecord | string | null | undefined): void {
        const record = this.#dependencies.resolvePluginRecord(plugin);
        if (!record?.name || !this.#dependencies.canExecutePluginAction(record)) return;
        const mode = resolveProviderMode(record);
        if (mode !== PROVIDER_MODE.USER_MANAGED) {
            const displayName = this.#dependencies.formatPluginName(record.displayName || record.name) || record.name;
            if (mode === PROVIDER_MODE.PLUGIN_MANAGED) {
                this.#dependencies.page.feedback.show(i18n.t('plugins.notifications.providerManagedReadOnly', { plugin: displayName }), 'info');
            } else {
                this.#dependencies.page.feedback.show(i18n.t('plugins.notifications.providersUnavailable', { plugin: displayName }), 'info');
            }
            return;
        }
        this.#dependencies.navigateToModels(MODELS_ACTION_ADD_PROVIDER, record);
    }

    async deletePlugin(pluginName: string): Promise<void> {
        await deletePluginWithStream(
            {
                deletingItems: this.#dependencies.collection.deletingItems,
                getCollectionRuntime: (): CollectionRuntime | null => this.#dependencies.collection.getCollectionRuntime(),
                getCatalogPlugin: (identifier: string): PluginRecord | null => this.#dependencies.collection.getCatalogPlugin(identifier),
                sanitizeText: (value: JsonValue | null | undefined): string => this.#dependencies.collection.sanitizeText(value),
                startDeleteStream: createPluginDeleteStreamStarter({
                    startTaskAction: (endpoint, options) => this.#dependencies.startTaskAction(endpoint, options)
                }),
                beginOptimisticOperation: (operation): void => this.#dependencies.collection.beginOptimisticOperation(operation),
                pageDom: this.#dependencies.page.pageDom
            },
            pluginName,
            async (options: ExecuteItemDeletionOptions): Promise<void> => {
                await this.executeItemDeletion(options);
            }
        );
    }

    async executeItemDeletion(options: ExecuteItemDeletionOptions): Promise<void> {
        await executeStreamItemDeletion(
            {
                deletingItems: this.#dependencies.collection.deletingItems,
                streams: this.#dependencies.collection.streams,
                optionalUI: (selector, context) => this.#dependencies.page.pageDom.optional(selector, context),
                addClassName: (element, className) => this.#dependencies.page.pageDom.addClass(element, className),
                removeClassName: (element, className) => this.#dependencies.page.pageDom.removeClass(element, className),
                showNotification: (message, type) => this.#dependencies.page.feedback.show(message, type),
                handleError: (error, title, config) => this.#dependencies.page.feedback.handle(error, title, config),
                renderItems: () => this.#dependencies.collection.renderItems(),
                removeItemById: (identifier) => this.#dependencies.collection.removeItemById(identifier)
            },
            {
                identifier: options.identifier,
                confirmTitle: options.confirmTitle,
                confirmMessage: options.confirmMessage,
                confirmButton: options.confirmButton,
                cancelButton: i18n.t('common.cancel'),
                getStream: options.getStream,
                gridSelector: options.gridSelector,
                findCard: options.findCard,
                pendingClass: options.pendingClass,
                successMessage: options.successMessage,
                ...(options.onAccepted ? { onAccepted: options.onAccepted } : {}),
                ...(options.projectLocally === undefined ? {} : { projectLocally: options.projectLocally })
            }
        );
    }

    async handleStopAllPlugins(): Promise<void> {
        await handleStopAllPluginsAction({
            getCollectionPlugins: (): PluginRecord[] => {
                const collection = this.#dependencies.collection.getCollectionRuntime();
                if (!collection) return [];
                const pluginsCandidate = collection.getAll();
                if (!isArray(pluginsCandidate)) return [];
                return pluginsCandidate.filter(isNamedPluginRecord);
            },
            isPluginStoppable: (plugin: PluginRecord): boolean => this.#dependencies.isPluginStoppable(plugin),
            updateStopAllButtonVisibility: (): void => this.#dependencies.updateStopAllButtonVisibility(),
            feedback: this.#dependencies.page.feedback,
            runPageTask: (taskKey, task, options) => this.#dependencies.runPageTask(taskKey, task, options),
            post: (path, body) => this.#dependencies.post(path, body)
        });
    }
}

export { PluginsOperationsController };
export type { PluginsOperationsControllerDependencies };
