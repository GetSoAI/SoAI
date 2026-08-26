/* SoAI - Models page modal integration service [frontend/assets/ts/pages/models/controllers/page/modalintegration/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getRequestAnimationFrame, getWindow } from '@core/environment/public.ts';
import { MODELS, PROVIDERS } from '@core/realtime/streammanager/resources/ids.ts';
import { serializeProviderSnapshotRequest } from '@core/plugins/pluginMutationContracts.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import type { EnsureCollectionStreamOptions } from '@core/routing/pages/pagetypes/public.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { requestWebSocketSnapshotArray } from '@core/websocketclient/snapshotPayload.ts';
import { decodeProvidersResource } from '@core/realtime/streammanager/resources/resourceDecoders.ts';
import { resolveOpenAIModalityDescriptor, resolveOpenAITokenDescriptor } from '@features/catalog/public.ts';
import { EditModelModalManager, MODELS_DOWNLOAD_MODAL_ID, MODELS_EDIT_MODEL_MODAL_ID, MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, MODELS_VIRTUAL_MODELS_MODAL_ID, ProvidersManager, createDownloadModalController, type DownloadModalHost } from '@features/models/public.ts';
import type { ModelsModalRuntimeDependencies } from '@pages/models/controllers/page/contracts.ts';
import type { ModelPropertyInput } from '@pages/models/controllers/modelsModelProperties.ts';
import { getPluginByName, isDownloadPluginOperational } from '@pages/models/controllers/page/effects.ts';
import { navigateToModelDetail } from '@pages/models/controllers/page/clickDispatch.ts';
import { createEditModelActionBridge } from '@pages/models/controllers/page/modalintegration/editModelActionsController.ts';
import { createVirtualModelsManager } from '@pages/models/controllers/page/modalintegration/virtualModelsManager.ts';
import type { ModelsModalManagerBundle } from '@pages/models/controllers/page/types.ts';
import type { VariantProbeManager } from '@pages/models/controllers/variantprobemanager/service.ts';
import { resolveModelStatusPresentation } from '@pages/models/rendering/cardrenderer/service.ts';

const createModelsModalManagers = (
    runtime: ModelsModalRuntimeDependencies,
    variantProbe: VariantProbeManager,
    modelProperties: {
        getModelPlugin(model: ModelPropertyInput): string;
        getModelStatus(statusManager: { normalizeStatus(status: JsonValue | null | undefined): string }, model: ModelPropertyInput): string;
        isExternalProviderModel(model: ModelPropertyInput): boolean;
        formatStrategyLabel(strategy: JsonValue | null | undefined): string;
    }
): ModelsModalManagerBundle => {
    const { infrastructure, session } = runtime;
    const downloadModalRoot = infrastructure.services.modals.requireElement(MODELS_DOWNLOAD_MODAL_ID);
    const editModelModalRoot = infrastructure.services.modals.requireElement(MODELS_EDIT_MODEL_MODAL_ID);
    const virtualModelsModalRoot = infrastructure.services.modals.requireElement(MODELS_VIRTUAL_MODELS_MODAL_ID);
    const vmEditModalRoot = infrastructure.services.modals.requireElement(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID);
    const normalizeUiValue = (value: JsonValue | null | undefined): string | null | undefined => {
        if (value === null || value === undefined) {
            return value;
        }
        return infrastructure.sanitizer.text(value, { allowEmpty: true });
    };
    const refreshJsonResource = async (resource: string, options?: EnsureCollectionStreamOptions): Promise<JsonValue | null> => {
        const refreshed = await infrastructure.streaming.runtime().resources.refresh(resource, options);
        return isJsonValue(refreshed) ? refreshed : null;
    };

    const providersManager = new ProvidersManager({
        modals: infrastructure.services.modals,
        optionalUI: (selector, context) => infrastructure.pageDom.optional(selector, context),
        queryUI: (selector, context) => infrastructure.pageDom.query(selector, context),
        showNotification: (message, type, options) => infrastructure.feedback.show(message, type, options),
        updateHTML: (element, html) => infrastructure.pageDom.updateHtml(element, html),
        addClassName: (target, className, context) => infrastructure.pageDom.addClass(target, className, context),
        removeClassName: (target, className, context) => infrastructure.pageDom.removeClass(target, className, context),
        consumeInitialActionContext: () => {
            const context = session.initialActionContext;
            session.initialActionContext = null;
            return context;
        },
        loadPlugins: (options) => runtime.catalog.load(options),
        getActiveProviderPlugins: () => session.providerPlugins.filter((plugin) => session.catalogStore.isProviderPluginOperational(plugin)),
        deleteProvider: (pluginName, providerId, revision) => infrastructure.api.plugins.providers.delete(pluginName, providerId, revision),
        getData: (element, key) => infrastructure.dom.getData(element, key),
        requestProviders: async (pluginName, signal) => {
            const payload = await requestWebSocketSnapshotArray(PROVIDERS, serializeProviderSnapshotRequest(pluginName), { signal });
            return decodeProvidersResource(payload);
        },
        subscribeProviderUpdate: (callback) => subscribeManagedWebSocketContract({ label: 'ProvidersManager', contract: WEBSOCKET_EVENT_CONTRACTS.provider.statusUpdated, handler: callback }),
        requestAnimationFrame: getRequestAnimationFrame(),
        setTimer: (callback, delayMs) => infrastructure.pageResources.setTimer(callback, delayMs),
        clearTimer: (timerId) => infrastructure.pageResources.clearTimer(timerId),
        sanitizer: infrastructure.sanitizer
    });

    const downloadModalHost: DownloadModalHost = {
        session: {
            modals: infrastructure.services.modals,
            requireHTMLElement: (selector, context) => infrastructure.pageDom.requireHTMLElement(selector, context ?? downloadModalRoot),
            requireUI: (selector, context) => infrastructure.pageDom.require(selector, context ?? downloadModalRoot),
            showNotification: (message, type, options) => infrastructure.feedback.show(message, type, options),
            api: infrastructure.api,
            dom: { hasClass: (target, className) => infrastructure.dom.hasClass(target, className) },
            sanitizer: infrastructure.sanitizer,
            getIconSync: (name, options) => infrastructure.services.getIconSync(name, options),
            isAdmin: () => infrastructure.auth.isAdmin(),
            consumeInitialActionContext: () => {
                const context = session.initialActionContext;
                session.initialActionContext = null;
                return context;
            },
            getClipboardService: () => infrastructure.services.clipboard(),
            copyToClipboard: (text, options) => infrastructure.services.copyToClipboard(text, options),
            setLocationHash: (hash) => {
                getWindow().location.hash = hash;
            }
        },
        execution: {
            streams: infrastructure.streaming.pageTracker,
            variantProbe,
            getAvailablePlugins: () => session.availablePlugins,
            refreshModelsAfterCatalogMutation: () => {
                infrastructure.pageLifecycle.runDetached('models:refreshAfterDownloadModalMutation', async () => {
                    await infrastructure.streaming.runtime().resources.refresh(MODELS, { allowDiscovery: true, throwOnError: true });
                });
            },
            requireStreamManager: () => ({
                ensureResourceStarted: async (key) => {
                    const resource = await infrastructure.streaming.runtime().resources.ensureResourceStarted(key);
                    return isJsonValue(resource) ? resource : null;
                },
                refresh: (resource, options) => refreshJsonResource(resource, options),
                hasActiveOperationsOfType: (type) => infrastructure.streaming.runtime().tasks.hasActiveOperationsOfType(type)
            }),
            createStreamHandlers: (_actionName, _message, callbacks) => infrastructure.streaming.handlers(callbacks),
            modelActions: runtime.modelActions
        },
        catalog: {
            loadPlugins: (options) => runtime.catalog.load(options),
            refreshPluginCaches: (plugins) => runtime.catalog.refresh(plugins),
            getDownloadPlugins: () => session.downloadPlugins,
            getProviderPlugins: () => session.providerPlugins,
            isDownloadPluginOperational: (plugin) => isDownloadPluginOperational(session.catalogStore, plugin),
            isProviderPluginOperational: (plugin) => session.catalogStore.isProviderPluginOperational(plugin),
            getPluginByName: (name) => getPluginByName(session, name),
            updateProviderButtonVisibility: () => providersManager.updateProviderButtonVisibility()
        },
        view: {
            optionalUI: (selector, context) => infrastructure.pageDom.optional(selector, context ?? downloadModalRoot),
            optionalHTMLElement: (selector, context) => infrastructure.pageDom.optionalHTMLElement(selector, context ?? downloadModalRoot),
            queryUI: (selector, context) => infrastructure.pageDom.query(selector, context ?? downloadModalRoot),
            setUIValue: (target, value, options, context) => {
                const scopeContext = context ?? downloadModalRoot;
                if (typeof target === 'string') {
                    const element = infrastructure.pageDom.optional(target, scopeContext);
                    if (element) {
                        infrastructure.pageElements.setValue(element, normalizeUiValue(value), options);
                    }
                    return;
                }
                infrastructure.pageElements.setValue(target, normalizeUiValue(value), options);
            },
            addClassName: (target, className, context) => infrastructure.pageDom.addClass(target, className, context ?? downloadModalRoot),
            removeClassName: (target, className, context) => infrastructure.pageDom.removeClass(target, className, context ?? downloadModalRoot),
            toggleClassName: (target, className, force, context) => infrastructure.pageDom.toggleClass(target, className, force, context ?? downloadModalRoot),
            updateHTML: (target, html, options, context) => infrastructure.pageDom.updateHtml(target, html, { ...(options ?? {}), context: context ?? downloadModalRoot }),
            updateText: (target, text, context) => infrastructure.pageDom.updateText(target, text, context ?? downloadModalRoot),
            updateProperty: (target, property, value, context) => infrastructure.pageDom.updateProperty(target, property, value, context ?? downloadModalRoot),
            updateAttribute: (target, attribute, value, context) => infrastructure.pageDom.updateAttribute(target, attribute, value, context ?? downloadModalRoot),
            updateStyle: (target, property, value, context) => infrastructure.pageDom.updateStyle(target, property, value, context ?? downloadModalRoot),
            setButtonLoading: (target, loading, options) => {
                infrastructure.stateManager.setButtonLoading(target, loading, options);
            }
        }
    };
    const downloadModalManager = createDownloadModalController({ host: downloadModalHost });

    const resolveEditModelStatusPresentation = (model: ModelRecord) =>
        resolveModelStatusPresentation(model, {
            status: {
                getModelStatus: (item) => modelProperties.getModelStatus(infrastructure.stateManager.status, item),
                presenter: infrastructure.stateManager.status,
                isExternalProviderModel: (item) => modelProperties.isExternalProviderModel(item)
            }
        });

    const virtualModelsManager = createVirtualModelsManager(runtime, { virtualModelsModalRoot, virtualModelEditModalRoot: vmEditModalRoot }, modelProperties);
    const editModelActionBridge = createEditModelActionBridge(runtime, modelProperties, virtualModelsManager);
    const editModelModalManager = new EditModelModalManager({
        host: {
            view: {
                modals: infrastructure.services.modals,
                requireHTMLElement: (selector, context) => infrastructure.pageDom.requireHTMLElement(selector, context ?? editModelModalRoot),
                optionalHTMLElement: (selector, context) => infrastructure.pageDom.optionalHTMLElement(selector, context ?? editModelModalRoot),
                runWithBoundary: (name, task) => infrastructure.pageLifecycle.run(name, task),
                showNotification: (message, type, options) => infrastructure.feedback.show(message, type, options),
                navigateToModelDetail: (model, options) => navigateToModelDetail(model, options, { router: infrastructure.router, onInvalidModel: (invalidModel) => runtime.log('error', `Invalid model or router unavailable: ${String(invalidModel.id ?? '')}`) }),
                showRenameModelModal: (model) => editModelActionBridge.showRenameModelModal(model),
                deleteModel: (model) => editModelActionBridge.deleteModel(model),
                updateText: (target, text) => infrastructure.pageDom.updateText(target, text),
                updateHTML: (target, html) => infrastructure.pageDom.updateHtml(target, html),
                toggleClassName: (target, className, force, context) => infrastructure.pageDom.toggleClass(target, className, force, context ?? editModelModalRoot),
                setModalBusy: (root, busy) => setAriaBusy(root, busy),
                resolveModelStatusBadgeClass: (model) => resolveEditModelStatusPresentation(model).badgeClass,
                resolveModelStatusLabel: (model) => resolveEditModelStatusPresentation(model).label
            },
            operations: {
                getClipboardService: () => infrastructure.services.clipboard(),
                copyToClipboard: (text, options) => infrastructure.services.copyToClipboard(text, options),
                getCapabilityManifest: () => session.catalogStore.getCapabilityManifest(),
                ensureCapabilityManifestReady: () => session.catalogStore.ensureCapabilityManifestReady(),
                findPluginRecord: (pluginName) => session.catalogStore.getPlugin(pluginName) ?? session.pluginLookup.get(pluginName) ?? null,
                resolveOpenAICapabilityLabel: (category, token) => (category === 'modalities' ? resolveOpenAIModalityDescriptor(token).label : resolveOpenAITokenDescriptor(category, token).label),
                api: infrastructure.api.models,
                refreshModelsCollection: async () => {
                    await infrastructure.streaming.runtime().resources.refresh(MODELS, { allowDiscovery: true, throwOnError: true });
                }
            }
        }
    });

    return { providersManager, downloadModalManager, editModelModalManager, renameModelModalManager: editModelActionBridge.renameModelModalManager, virtualModelsManager };
};
export { createModelsModalManagers };
