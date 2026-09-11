/* SoAI - Models page control layer adapters [frontend/assets/ts/pages/models/controllers/page/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { resolveModelRequestCount, resolveModelTokenCount } from '@core/models/usageMetrics.ts';
import { createCardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';
import { modelsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import { isObject } from '@core/typeGuards.ts';
import type { CatalogStore } from '@features/catalog/public.ts';
import { MODELS_DOWNLOAD_MODAL_ID } from '@features/models/public.ts';
import { ACTIVE_MODEL_STATUSES } from '@pages/models/contracts/ModelPageSupport.ts';
import { createModelsModelProperties, resolveModelsItemCardId } from '@pages/models/controllers/modelsModelProperties.ts';
import type { ModelsManagerRuntimeDependencies } from '@pages/models/controllers/page/contracts.ts';
import { getPluginByName } from '@pages/models/controllers/page/effects.ts';
import { createModelsModalManagers } from '@pages/models/controllers/page/modalintegration/service.ts';
import { VariantProbeManager } from '@pages/models/controllers/variantprobemanager/service.ts';
import type { VariantProbeHost } from '@pages/models/controllers/variantprobemanager/types.ts';
import { ModelCardRenderer } from '@pages/models/rendering/CardRenderer.ts';
import type { ModelCardHost } from '@pages/models/rendering/cardrenderer/types.ts';

interface ModelsManagerInitializationResult {
    catalogStore: CatalogStore;
    catalogSubscriptions: ModelsManagerRuntimeDependencies['catalog']['subscriptions'];
    modelProperties: ReturnType<typeof createModelsModelProperties>;
    variantProbe: VariantProbeManager;
    modelCardHost: ModelCardHost;
    cardRenderer: ModelCardRenderer;
    cardController: ReturnType<typeof createCardPageController>;
    providersManager: ReturnType<typeof createModelsModalManagers>['providersManager'];
    downloadModalManager: ReturnType<typeof createModelsModalManagers>['downloadModalManager'];
    editModelModalManager: ReturnType<typeof createModelsModalManagers>['editModelModalManager'];
    renameModelModalManager: ReturnType<typeof createModelsModalManagers>['renameModelModalManager'];
    virtualModelsManager: ReturnType<typeof createModelsModalManagers>['virtualModelsManager'];
}

interface ModelsManagerBundleOptions {
    getPendingToggleTarget?: ModelCardHost['status']['getPendingToggleTarget'] | undefined;
    shouldShowNormalEmptyState: (modelCount: number) => boolean;
}

const createModelsManagerBundle = (runtime: ModelsManagerRuntimeDependencies, options: ModelsManagerBundleOptions): ModelsManagerInitializationResult => {
    const { infrastructure, session, collection } = runtime;
    const downloadModalRoot = infrastructure.services.modals.requireElement(MODELS_DOWNLOAD_MODAL_ID);
    const variantProbeHost: VariantProbeHost = {
        sanitizer: infrastructure.sanitizer,
        formatNumber: (value, options) => i18n.formatNumber(value, options),
        getIconSync: (iconName, options) => infrastructure.services.getIconSync(iconName, options),
        pageDom: infrastructure.pageDom,
        setUIValue: (target, value, options) => infrastructure.pageElements.setValue(target, value, options)
    };
    const variantProbe = new VariantProbeManager({ host: variantProbeHost, speedTest: runtime.speedTest, modalId: MODELS_DOWNLOAD_MODAL_ID, modalRoot: downloadModalRoot });
    const modelProperties = createModelsModelProperties({
        getIconSync: (iconName, options) => infrastructure.services.getIconSync(iconName, options),
        getPluginByName: (name) => getPluginByName(session, name),
        isProviderPluginOperational: (plugin) => session.catalogStore.isProviderPluginOperational(plugin)
    });

    const modelCardHost: ModelCardHost = {
        dom: { createFragment: (html) => infrastructure.dom.createFragment(html) },
        sanitizeClassName: (value, fallback, options) => infrastructure.services.sanitizeClassName(value, fallback, options),
        presentation: {
            sanitizeText: (value, options) => infrastructure.services.sanitizeText(value, options),
            getIconSync: (name, options) => infrastructure.services.getIconSync(name, options),
            getModelIcon: (model, pluginName) => modelProperties.getModelIcon(model, pluginName)
        },
        identity: {
            getItemCardId: (model) => resolveModelsItemCardId(model),
            getModelPlugin: (model) => modelProperties.getModelPlugin(model),
            getModelProvider: (model) => modelProperties.getModelProvider(model),
            getModelOriginId: (model) => modelProperties.getModelOriginId(model),
            extractCleanModelId: (id) => modelProperties.extractCleanModelId(id),
            getModelDisplayName: (model) => modelProperties.getModelDisplayName(model)
        },
        status: {
            getModelStatus: (model) => modelProperties.getModelStatus(infrastructure.stateManager.status, model),
            presenter: infrastructure.stateManager.status,
            getPendingToggleTarget: (model) => options.getPendingToggleTarget?.(model) ?? null,
            canDeleteModel: (model) => modelProperties.canDeleteModel(model),
            isExternalProviderModel: (model) => modelProperties.isExternalProviderModel(model),
            isModelFromPersistentPlugin: (model) => {
                const pluginName = modelProperties.getModelPlugin(model);
                return Boolean(pluginName && getPluginByName(session, pluginName)?.isPersistent);
            },
            isNewItem: (model) => session.recentItems.isMarked(resolveModelsItemCardId(model))
        },
        metrics: {
            formatStrategyLabel: (strategy) => modelProperties.formatStrategyLabel(strategy),
            formatNumber: (value, options) => i18n.formatNumber(value, options),
            resolveModelRequestCount: (model) => resolveModelRequestCount(session.currentMetrics, model),
            resolveModelTokenCount: (model) => resolveModelTokenCount(session.currentMetrics, model)
        }
    };
    const cardRenderer = new ModelCardRenderer({ host: modelCardHost, activeStatuses: ACTIVE_MODEL_STATUSES });

    const grid = modelsPageConfig.grid;
    const cardController = createCardPageController(
        {
            dom: {
                getData: (element, key) => infrastructure.dom.getData(element, key),
                setData: (element, key, value) => infrastructure.dom.setData(element, key, value)
            },
            optionalUI: (selector) => infrastructure.pageDom.optional(selector),
            toggleHidden: (element, hidden) => infrastructure.pageDom.toggleClass(element, 'u-hidden', hidden),
            flushDOMUpdates: () => infrastructure.pageDom.flush(),
            queueResponsiveLayoutUpdate: () => infrastructure.layout.queueResponsive()
        },
        {
            dataKey: modelsPageConfig.dataKey,
            itemLabel: modelsPageConfig.itemLabel,
            collectionName: modelsPageConfig.collectionName,
            cardSelector: grid.cardSelector,
            gridSelector: grid.gridSelector,
            getItemId: (model) => {
                if (!isObject(model)) {
                    return null;
                }
                const id = resolveModelsItemCardId(model);
                return id ? String(id) : null;
            },
            resolveCurrentItem: (identifier) => collection.collections.runtime?.find(identifier) ?? null,
            emptyStates: [
                { selector: grid.emptyStateIds.empty, visibleWhen: ({ all }) => options.shouldShowNormalEmptyState(all.length) },
                {
                    selector: grid.emptyStateIds.filtered,
                    visibleWhen: ({ filtered, all }) => all.length > 0 && filtered.length === 0
                }
            ]
        }
    );

    const catalogStore = session.catalogStore;
    const catalogSubscriptions = runtime.catalog.subscriptions;

    const { providersManager, downloadModalManager, editModelModalManager, renameModelModalManager, virtualModelsManager } = createModelsModalManagers(runtime, variantProbe, modelProperties);
    session.cardRenderer = cardRenderer;
    session.cardController = cardController;

    return {
        catalogStore,
        catalogSubscriptions,
        modelProperties,
        variantProbe,
        modelCardHost,
        cardRenderer,
        cardController,
        providersManager,
        downloadModalManager,
        editModelModalManager,
        renameModelModalManager,
        virtualModelsManager
    };
};

export { createModelsManagerBundle };
export type { ModelsManagerInitializationResult };
