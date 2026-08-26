/* SoAI - Models page stats controller [frontend/assets/ts/pages/models/controllers/modelsStatsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceSelectOptions } from '@core/dom/selectOptions.ts';
import { i18n } from '@core/i18n/index.ts';
import { uniqueSortedStrings } from '@core/normalize.ts';
import { getPageControlSelectOptionValues, syncPageControlSelectValue } from '@core/pagecontrols/selectController.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { capitalize } from '@core/primitives/text.ts';
import { isObject } from '@core/typeGuards.ts';
import type { ResourceItem } from '@core/data/ClientDataHub.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { LatestUsageResource } from '@core/realtime/streammanager/resources/latestUsageResource.ts';
import { MODELS_ACTION_MANAGE_VIRTUAL_MODELS } from '@core/models/pageActions.ts';
import type { ModelPropertyInput } from '@pages/models/controllers/modelsModelProperties.ts';
import { normalizeModelRecordStrict } from '@pages/models/controllers/page/state.ts';

interface ModelsStatsControllerDependencies {
    optionalUI: (selector: string) => Element | null;
    updateText: (element: Element, text: string) => void;
    toggleClassName: (element: Element, className: string, enabled: boolean) => void;
    updateHeaderStat: (id: string, label: string, value: number | string) => void;
    queueResponsiveLayoutUpdate: () => void;
    getProviderPlugins: () => PluginRecord[];
    getModelStatus: (model: ModelPropertyInput) => string;
    isExternalProviderModel: (model: ModelPropertyInput) => boolean;
    getModelPlugin: (model: ModelPropertyInput) => string;
    models: {
        getAll: () => ModelRecord[];
        find: (universalId: string) => ModelRecord | null;
    };
    getModelDisplayName: (model: ModelPropertyInput) => string;
    getCollectionAllRaw: () => ResourceItem[];
    resolveModelRequestCount: (model: ModelRecord) => number;
    getAvailablePluginsCount: () => number;
    getFilterProvider: () => string;
    setFilterProvider: (value: string) => void;
    persistFilterProvider: (value: string) => void;
    reapplyCollection: () => void;
    updateProviderButtonVisibility: () => void;
}

interface ModelsStatsController {
    updateStats: () => void;
    populateProviderFilter: () => void;
    updateVirtualModelsButtonVisibility: () => void;
    updateLastUsedStat: (latestUsage?: LatestUsageResource) => void;
}

const createModelsStatsController = (dependencies: ModelsStatsControllerDependencies): ModelsStatsController => {
    const headerSignatures = new Map<string, string>();
    let totalSizeText: string | null = null;
    let virtualModelsButtonHidden: boolean | null = null;
    let virtualModelsButtonElement: Element | null = null;
    let currentLatestUsage: LatestUsageResource | null = null;

    const applyLastUsedStat = (latestUsage?: LatestUsageResource): boolean => {
        if (latestUsage !== undefined) currentLatestUsage = latestUsage;
        const identity = currentLatestUsage?.identity ?? null;
        const model = identity ? dependencies.models.find(identity) : null;
        const resolvedName = model ? dependencies.getModelDisplayName(model) : '';
        const value = resolvedName || identity || i18n.t('common.notAvailableShort');
        const label = i18n.t('models.stats.lastUsedModel');
        const signature = `${label}\n${value}`;
        if (headerSignatures.get('last-used-model') === signature) return false;
        headerSignatures.set('last-used-model', signature);
        dependencies.updateHeaderStat('last-used-model', label, value);
        return true;
    };

    const updateLastUsedStat = (latestUsage?: LatestUsageResource): void => {
        if (applyLastUsedStat(latestUsage)) dependencies.queueResponsiveLayoutUpdate();
    };

    const updateVirtualModelsButtonVisibility = (): void => {
        const button = dependencies.optionalUI(MODELS_ACTION_MANAGE_VIRTUAL_MODELS);
        if (!button) return;
        const hidden = dependencies.getAvailablePluginsCount() === 0;
        if (virtualModelsButtonElement === button && virtualModelsButtonHidden === hidden) return;
        virtualModelsButtonElement = button;
        virtualModelsButtonHidden = hidden;
        dependencies.toggleClassName(button, 'u-hidden', hidden);
    };

    const updateStats = (): void => {
        const stats = { total: 0, local: 0, virtual: 0, loaded: 0, totalSize: 0, requests: 0, orphaned: 0 };
        const all = dependencies.getCollectionAllRaw();
        for (const entry of all) {
            if (!isObject(entry)) continue;
            stats.total++;
            const sizeValue = entry['sizeBytes'];
            stats.totalSize += typeof sizeValue === 'number' ? sizeValue : 0;
            const modelRecord = normalizeModelRecordStrict(entry, 'ModelsStatsController.updateStats');
            stats.requests += dependencies.resolveModelRequestCount(modelRecord);
            if (entry['type'] === 'virtual') stats.virtual++;
            else if (!dependencies.isExternalProviderModel(entry)) stats.local++;
            if (entry['isOrphaned'] === true) stats.orphaned++;
            if (dependencies.getModelStatus(entry) === 'READY') stats.loaded++;
        }

        const providerCount = dependencies.getProviderPlugins().reduce((total, plugin) => {
            const pluginStatsRaw = plugin['stats'];
            const pluginStats = isObject(pluginStatsRaw) ? pluginStatsRaw : null;
            const countValue = pluginStats?.providerCount;
            return total + (typeof countValue === 'number' ? countValue : 0);
        }, 0);

        const displayedStats = [
            { id: 'total-models', label: i18n.plural('models.stats.totalModels', stats.total, { count: stats.total }), value: stats.total },
            { id: 'local-models', label: i18n.plural('models.stats.local_models', stats.local, { count: stats.local }), value: stats.local },
            { id: 'virtual-models', label: i18n.plural('models.stats.virtualModels', stats.virtual, { count: stats.virtual }), value: stats.virtual },
            { id: 'loaded-models', label: i18n.plural('models.stats.loaded', stats.loaded, { count: stats.loaded }), value: stats.loaded },
            { id: 'external-models', label: i18n.plural('models.stats.externalProviders', providerCount, { count: providerCount }), value: providerCount },
            { id: 'requests-total', label: i18n.plural('models.stats.requests', stats.requests, { count: stats.requests }), value: stats.requests }
        ];
        let presentationChanged = false;
        for (const displayed of displayedStats) {
            const signature = `${displayed.label}\n${displayed.value}`;
            if (headerSignatures.get(displayed.id) === signature) continue;
            headerSignatures.set(displayed.id, signature);
            dependencies.updateHeaderStat(displayed.id, displayed.label, displayed.value);
            presentationChanged = true;
        }

        const totalSizeElement = dependencies.optionalUI('total-size');
        const nextTotalSizeText = formatBytes(stats.totalSize);
        if (totalSizeElement && totalSizeText !== nextTotalSizeText) {
            totalSizeText = nextTotalSizeText;
            dependencies.updateText(totalSizeElement, nextTotalSizeText);
            presentationChanged = true;
        }

        dependencies.updateProviderButtonVisibility();
        if (applyLastUsedStat()) presentationChanged = true;
        const previousVirtualModelsButtonHidden = virtualModelsButtonHidden;
        updateVirtualModelsButtonVisibility();
        if (previousVirtualModelsButtonHidden !== virtualModelsButtonHidden) presentationChanged = true;
        if (presentationChanged) dependencies.queueResponsiveLayoutUpdate();
    };

    const populateProviderFilter = (): void => {
        const filter = dependencies.optionalUI('provider-filter');
        if (!filter) return;
        if (!(filter instanceof HTMLSelectElement)) {
            throw new TypeError('Models provider filter must be an HTMLSelectElement');
        }
        const models = dependencies.models.getAll();
        const plugins = uniqueSortedStrings(models.map((model) => dependencies.getModelPlugin(model)).filter(Boolean), 'en');
        const currentFilterProvider = dependencies.getFilterProvider();
        replaceSelectOptions(filter, [
            { value: 'all', label: i18n.t('models.filters.allPlugins') },
            ...plugins.map((plugin) => ({
                value: plugin,
                label: capitalize(plugin)
            }))
        ]);
        const selectedFilterProvider = syncPageControlSelectValue(filter, currentFilterProvider, getPageControlSelectOptionValues(filter), 'all').visibleValue;
        if (selectedFilterProvider !== currentFilterProvider) {
            dependencies.setFilterProvider(selectedFilterProvider);
            dependencies.persistFilterProvider(selectedFilterProvider);
            dependencies.reapplyCollection();
        }
    };

    return {
        updateStats,
        populateProviderFilter,
        updateVirtualModelsButtonVisibility,
        updateLastUsedStat
    };
};

export { createModelsStatsController };
export type { ModelsStatsController, ModelsStatsControllerDependencies };
