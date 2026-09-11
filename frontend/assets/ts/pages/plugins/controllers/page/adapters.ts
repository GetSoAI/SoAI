/* SoAI - Plugins page adapters [frontend/assets/ts/pages/plugins/controllers/page/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { getWindow } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import type { StreamHandlerCallbacks } from '@core/routing/pages/pagetypes/public.ts';
import { resolveHttpsWebsiteUrl, securityApi } from '@core/security/public.ts';
import type { EscapeSanitizerApi } from '@core/security/protocols.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { BackendVariantsResponse, PluginBackendUpdatesResponse, PluginBackendUpdateStatus } from '@core/api/contracts/pluginManagementContracts.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { getCapabilityDescriptors } from '@features/catalog/public.ts';
import { createPluginsManagerHostCallbacks, createPluginsModalManagers, type BackendTaskActionOptions, type BackendTaskCommandOptions, type ConfigurationManager, type PluginsManagerHostCallbacks, type ProgressReporter } from '@features/plugins/public.ts';
import type { PluginsPageControllerSet, PluginsPageModalManagers } from '@pages/plugins/controllers/contracts.ts';
import { isConfigurationManager, type CreatePluginsPageRuntimeDependencies, type PluginsControllerResolvers } from '@pages/plugins/controllers/page/contracts.ts';
import type { PluginsProgressController } from '@pages/plugins/controllers/progressController.ts';
import { handlePluginsBackendWebsiteLinkClick } from '@pages/plugins/formatting/pluginsExternalLink.ts';

interface CreatePluginsPageModalRuntimeDependencies {
    dependencies: CreatePluginsPageRuntimeDependencies;
    resolvers: PluginsControllerResolvers;
    coreControllers: Pick<PluginsPageControllerSet, 'compatibilityController' | 'dataController' | 'collectionController' | 'statsController' | 'taskActionController'>;
    progressController: PluginsProgressController;
    showNotification(message: string, type?: NotificationType, duration?: number): void;
}

interface PluginsPageModalRuntime {
    managerHostCallbacks: PluginsManagerHostCallbacks;
    modalManagers: PluginsPageModalManagers;
}

const normalizeStringOptionRecord = (options: Record<string, JsonValue | null | undefined> | undefined): Record<string, string | null> | undefined => {
    if (!options) return undefined;
    const normalized: Record<string, string | null> = {};
    for (const [key, value] of Object.entries(options)) {
        normalized[key] = value === null || value === undefined ? null : String(value);
    }
    return normalized;
};

const normalizeJsonRecord = (options: Record<string, JsonValue | null | undefined>): JsonObject => {
    const normalized: JsonObject = {};
    for (const [key, value] of Object.entries(options)) {
        normalized[key] = value === undefined ? null : value;
    }
    return normalized;
};

const normalizeOperationMeta = (operation: BackendTaskActionOptions['operation'] | BackendTaskCommandOptions['operation'] | null | undefined): JsonObject | null => {
    if (operation === null || operation === undefined) return null;
    const value = toJsonCompatibleValue(operation);
    if (!isJsonObject(value)) {
        throw new Error('Plugin task operation metadata must be a JSON object');
    }
    return value;
};

const normalizeBackendTaskActionOptions = (options: BackendTaskActionOptions): { method?: string; body?: JsonValue | null | undefined; handlers?: BackendTaskActionOptions['handlers']; operation?: JsonObject | null } => ({
    ...(options.method === undefined ? {} : { method: options.method }),
    ...(options.body === undefined ? {} : { body: options.body }),
    handlers: options.handlers,
    operation: normalizeOperationMeta(options.operation)
});

const normalizeBackendTaskCommandOptions = (options: BackendTaskCommandOptions): { handlers?: BackendTaskCommandOptions['handlers']; operation?: JsonObject | null } => ({
    handlers: options.handlers,
    operation: normalizeOperationMeta(options.operation)
});

const normalizeModalStreamCallbacks = (callbacks: { onProgress?: (data: JsonValue | undefined) => void; onComplete?: (data: JsonValue | undefined) => void; onError?: (error: Error) => void } | undefined): StreamHandlerCallbacks | undefined => {
    if (!callbacks) return undefined;
    return {
        ...(callbacks.onProgress ? { onProgress: (data: JsonValue | null): void => callbacks.onProgress?.(data ?? undefined) } : {}),
        ...(callbacks.onComplete ? { onComplete: (data: JsonValue | null): void => callbacks.onComplete?.(data ?? undefined) } : {}),
        ...(callbacks.onError ? { onError: (error: Error | JsonValue | null): void => callbacks.onError?.(ensureError(error)) } : {})
    };
};

const createPluginsPageModalRuntime = (dependencies: CreatePluginsPageModalRuntimeDependencies): PluginsPageModalRuntime => {
    const { resolvers, coreControllers, progressController, showNotification } = dependencies;
    const { infrastructure, collection, pageDependencies, session } = dependencies.dependencies;
    const sanitizerAdapter: EscapeSanitizerApi = {
        escapeHtml: securityApi.escapeHtml,
        escapeAttribute: securityApi.escapeAttribute,
        sanitizeUrl: securityApi.sanitizeUrl,
        sanitizeAbsoluteHttpUrl: securityApi.sanitizeAbsoluteHttpUrl,
        resolveHttpsWebsiteUrl
    };

    const managerHostCallbacks = createPluginsManagerHostCallbacks({
        modals: infrastructure.services.modals,
        requireHTMLElement: (selector: string | Element, context?: Element): HTMLElement => infrastructure.pageDom.requireHTMLElement(selector, context),
        optionalHTMLElement: (selector: string | Element, context?: Element): HTMLElement | null => infrastructure.pageDom.optionalHTMLElement(selector, context),
        queryUI: (selector: string | Element | string[], context?: Element): Element[] => infrastructure.pageDom.query(selector, context),
        on: (target: EventTarget | Element, event: string, handler: EventListener, options?: AddEventListenerOptions) => {
            const dispose = infrastructure.pageResources.on(target, event, handler, options);
            return isFunction(dispose) ? dispose : (): void => {};
        },
        updateText: (target: Element | string, text: string): void => infrastructure.pageDom.updateText(target, text),
        updateHTML: (target: Element | string, html: string, options?: { escape?: boolean; context?: Element | Document | null }): void => infrastructure.pageDom.updateHtml(target, html, options),
        addClassName: (target: Element | string, classes: string | string[]): void => infrastructure.pageDom.addClass(target, classes),
        removeClassName: (target: Element | string, classes: string | string[]): void => infrastructure.pageDom.removeClass(target, classes),
        setUIValue: (target: Element | string, value: JsonValue | null | undefined, options?: { attribute?: string }): void => infrastructure.pageElements.setValue(target, value === null || value === undefined ? value : String(value), options),
        updateProperty: (target: Element | string, property: string, value: DomPropertyValue): void => infrastructure.pageDom.updateProperty(target, property, value),
        updateAttribute: (target: Element | string, attribute: string, value: string | null): void => infrastructure.pageDom.updateAttribute(target, attribute, value),
        toggleClassName: (target: Element | string, className: string, force?: boolean): void => infrastructure.pageDom.toggleClass(target, className, force),
        setDataAttribute: (target: Element | string, name: string, value: string | null): void => infrastructure.pageDom.setDataAttribute(target, name, value),
        timing: {
            setTimeout: (callback: (() => void) | undefined, delay: number): number | null => (callback ? infrastructure.pageResources.setTimeout(callback, delay) : null),
            clearTimer: (timerId: number | null | undefined): void => infrastructure.pageResources.clearTimer(timerId ?? null)
        },
        createConfigurationManager: (): ConfigurationManager => {
            const manager = infrastructure.services.createConfigurationManager();
            if (!isConfigurationManager(manager)) {
                throw new Error('PluginsPage configuration manager is invalid');
            }
            return manager;
        },
        copyToClipboard: async (value: string, options?: { notify(message: string, type: string): void }): Promise<void> => {
            await infrastructure.services.copyToClipboard(value, options);
        },
        sanitizeText: (value: JsonValue | null | undefined, options?: Record<string, JsonValue | null | undefined>): string => infrastructure.services.sanitizeText(value === null || value === undefined ? value : String(value), normalizeStringOptionRecord(options)),
        sanitizeClassName: (value: JsonValue | null | undefined, fallback: string | Record<string, JsonValue | null | undefined>, mapping?: Record<string, JsonValue | null | undefined>): string => infrastructure.services.sanitizeClassName(value === null || value === undefined ? value : String(value), typeof fallback === 'string' ? fallback : (normalizeStringOptionRecord(fallback) ?? {}), normalizeStringOptionRecord(mapping)),
        showNotification
    });

    const pluginsApi = infrastructure.api.plugins;
    if (!pluginsApi.checkUpdates) {
        throw new Error('Plugins API checkUpdates is unavailable');
    }
    const modalManagers = createPluginsModalManagers({
        foundation: {
            callbacks: managerHostCallbacks,
            security: sanitizerAdapter,
            statusManager: infrastructure.stateManager.status,
            dom: {
                getData: (element: Element, key: string): string | null => infrastructure.dom.getData(element, key),
                setData: (element: Element, key: string, value: string): void => infrastructure.dom.setData(element, key, value)
            },
            streams: infrastructure.streaming.pageTracker,
            api: infrastructure.api
        },
        concurrency: {
            getRestartOverlay: () => pageDependencies.restartOverlay,
            getMaxConcurrentPlugins: (): number | null => session.maxConcurrentPlugins,
            setMaxConcurrentPlugins: (value: number | null): void => {
                session.maxConcurrentPlugins = value;
            },
            getConcurrentPluginsOriginalValue: (): number | null => session.concurrentPluginsOriginalValue,
            setConcurrentPluginsOriginalValue: (value: number | null): void => {
                session.concurrentPluginsOriginalValue = value;
            },
            getCoreConfigCache: () => session.coreConfigCache,
            setCoreConfigCache: (value): void => {
                session.coreConfigCache = value;
            }
        },
        operations: {
            updateStats: (): void => coreControllers.statsController.updateStats(),
            loadCoreConfig: (options?: { force?: boolean }): Promise<void> => {
                const lifecycleController = resolvers.getLifecycleController();
                if (!lifecycleController) {
                    throw new Error('Plugins lifecycle controller is not initialized');
                }
                return lifecycleController.loadCoreConfig(options);
            },
            createStreamHandlers: (_key, _message, callbacks) => infrastructure.streaming.handlers(normalizeModalStreamCallbacks(callbacks)),
            trackAcceptedTask: (taskId, options) =>
                infrastructure.streaming.runtime().tasks.trackAcceptedTask(taskId, {
                    handlers: options.handlers,
                    operation: normalizeOperationMeta(options.operation),
                    ...(options.timeoutMs === undefined ? {} : { timeoutMs: options.timeoutMs })
                }),
            startTaskAction: (endpoint, options, runtimeOptions) => infrastructure.streaming.taskAction(endpoint, normalizeBackendTaskActionOptions(options), runtimeOptions),
            startTaskCommand: (command, options, runtimeOptions) => {
                if (!isJsonObject(command)) {
                    throw new Error('Plugin task command must be JSON');
                }
                return infrastructure.streaming.taskCommand(command, normalizeBackendTaskCommandOptions(options), runtimeOptions);
            },
            beginOptimisticOperation: (operation): void => session.catalogStore.beginOptimisticOperation(operation),
            cancelDownload: (key: string): void => collection.cancelDownload(key),
            createOperationProgressReporter: (containerId: string, options: { onCancel(key: string): void; backgroundButtonId?: string }): ProgressReporter | null => infrastructure.streaming.progressReporter(containerId, options),
            hasClipboardSupport: (): boolean => infrastructure.services.hasClipboardSupport(),
            isAdmin: (): boolean => infrastructure.auth.isAdmin(),
            setLocationHash: (hash: string): void => {
                getWindow().location.hash = hash;
            }
        },
        presentation: {
            getCapabilityDescriptors: (plugin: PluginRecord) => getCapabilityDescriptors(plugin),
            checkBackendInstallationSupport: (plugin: PluginRecord): boolean => {
                const operationsController = resolvers.getOperationsController();
                if (!operationsController) {
                    throw new Error('Plugins operations controller is not initialized');
                }
                return operationsController.checkBackendInstallationSupport(plugin);
            },
            isPluginPermanentlyDisabled: (plugin: PluginRecord): boolean => coreControllers.dataController.isPluginPermanentlyDisabled(plugin),
            notifyPluginIncompatible: (plugin: PluginRecord): void => coreControllers.compatibilityController.notifyPluginIncompatible(plugin),
            handleBackendWebsiteLinkClick: (event: Event): Promise<void> => handlePluginsBackendWebsiteLinkClick(event, { feedback: infrastructure.feedback }),
            getBackendStatus: (plugin: PluginRecord): string => coreControllers.dataController.getBackendStatus(plugin),
            getBackendVersion: (plugin: PluginRecord): string => String(coreControllers.dataController.resolvePluginRecord(plugin)?.backendVersion ?? '').trim(),
            getPluginStatus: (plugin: PluginRecord): string => coreControllers.dataController.getPluginStatus(plugin),
            formatPluginName: (name: string): string => coreControllers.dataController.formatPluginName(name)
        },
        state: {
            subscribeModalLedUpdates: (): void => progressController.subscribeModalLedUpdates(),
            unsubscribeModalLedUpdates: (): void => progressController.unsubscribeModalLedUpdates(),
            setCurrentManagingPlugin: (plugin: PluginRecord | null): void => {
                session.currentManagingPlugin = plugin;
            },
            setCurrentUpdateInfo: (info: PluginBackendUpdateStatus | null): void => {
                session.currentUpdateInfo = info;
            }
        },
        updates: {
            normalizeVersion: (value: JsonValue | null | undefined) => coreControllers.dataController.normalizeVersion(value),
            checkUpdates: async (): Promise<PluginBackendUpdatesResponse> => pluginsApi.checkUpdates(),
            getBackendVariants: async (pluginName: string): Promise<BackendVariantsResponse> => pluginsApi.getBackendVariants(pluginName),
            saveBackendVariantSelection: async (pluginName: string, variantId: string): Promise<BackendVariantsResponse> => pluginsApi.saveBackendVariantSelection(pluginName, variantId)
        },
        progress: {
            setPluginProgressMeta: (key: string, meta: Record<string, JsonValue | null | undefined>): void => progressController.setPluginProgressMeta(key, normalizeJsonRecord(meta)),
            consumePluginProgressMeta: (key: string): Record<string, JsonValue | null | undefined> | null => progressController.consumePluginProgressMeta(key),
            isPluginIncompatible: (plugin: PluginRecord): boolean => coreControllers.dataController.isPluginIncompatible(plugin)
        }
    });
    return { managerHostCallbacks, modalManagers };
};

export { createPluginsPageModalRuntime };
export type { CreatePluginsPageModalRuntimeDependencies, PluginsPageModalRuntime };
