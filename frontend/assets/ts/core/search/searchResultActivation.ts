/* SoAI - Search result navigation resolution [frontend/assets/ts/core/search/searchResultActivation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { encodeSegment } from '@core/identifiers.ts';
import { buildFileExplorerDeepLinkQuery } from '@core/fileexplorerbrowser/deepLinks.ts';
import { basenameVirtualPath, parentVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { normalizeSearchCategory } from '@core/search/searchCategory.ts';
import { buildSettingsConfigPathDeepLinkQuery } from '@core/settings/configPathDeepLink.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { isString } from '@core/typeGuards.ts';

interface SearchItemDataset {
    type?: string;
    id?: string;
    plugin?: string;
    component?: string;
    gpuIndex?: string;
    identifier?: string;
    metric?: string;
    filePath?: string;
    fileEntryType?: string;
    configPath?: string;
}

interface SearchResultNavigationCommand {
    route: string;
    query?: Record<string, string>;
}

interface SearchResultDatasetAttribute {
    field: keyof SearchItemDataset;
    attribute: string;
}

const SEARCH_RESULT_DATASET_ATTRIBUTES: readonly SearchResultDatasetAttribute[] = [
    { field: 'type', attribute: 'data-type' },
    { field: 'id', attribute: 'data-id' },
    { field: 'plugin', attribute: 'data-plugin' },
    { field: 'component', attribute: 'data-component' },
    { field: 'gpuIndex', attribute: 'data-gpu-index' },
    { field: 'identifier', attribute: 'data-identifier' },
    { field: 'metric', attribute: 'data-metric' },
    { field: 'filePath', attribute: 'data-file-path' },
    { field: 'fileEntryType', attribute: 'data-file-entry-type' },
    { field: 'configPath', attribute: 'data-config-path' }
];

const readDatasetText = (value: string | null | undefined): string => (isString(value) ? value.trim() : '');

const MODAL_SEARCH_TARGETS: Readonly<Record<string, SearchResultNavigationCommand>> = Object.freeze({
    'add-model': { route: 'models', query: { action: 'download-model' } },
    'add-plugin': { route: 'plugins', query: { modal: 'add-plugin' } },
    'add-automation': { route: 'automation', query: { modal: 'add-automation' } },
    'add-mcp-server': { route: 'settings', query: { tab: 'mcp', modal: 'add-mcp-server' } },
    'chat-settings': { route: 'chat', query: { modal: 'chat-settings' } }
});

const POWER_ACTION_TARGETS: Readonly<Record<string, SearchResultNavigationCommand>> = Object.freeze({
    restartApplication: { route: 'power', query: { action: 'restartApplication' } },
    shutdownApplication: { route: 'power', query: { action: 'shutdownApplication' } },
    rebootSystem: { route: 'power', query: { action: 'rebootSystem' } },
    shutdownSystem: { route: 'power', query: { action: 'shutdownSystem' } },
    suspendSystem: { route: 'power', query: { action: 'suspendSystem' } },
    hibernateSystem: { route: 'power', query: { action: 'hibernateSystem' } }
});

const readSearchResultDataset = (dataset: DOMStringMap): SearchItemDataset => {
    const result: SearchItemDataset = {};
    const typeValue = dataset['type'];
    if (typeValue) result.type = typeValue;
    const idValue = dataset['id'];
    if (idValue) result.id = idValue;
    const pluginValue = dataset['plugin'];
    if (pluginValue) result.plugin = pluginValue;
    const componentValue = dataset['component'];
    if (componentValue) result.component = componentValue;
    const gpuIndexValue = dataset['gpuIndex'];
    if (gpuIndexValue) result.gpuIndex = gpuIndexValue;
    const identifierValue = dataset['identifier'];
    if (identifierValue) result.identifier = identifierValue;
    const metricValue = dataset['metric'];
    if (metricValue) result.metric = metricValue;
    const filePathValue = dataset['filePath'];
    if (filePathValue) result.filePath = filePathValue;
    const fileEntryTypeValue = dataset['fileEntryType'];
    if (fileEntryTypeValue) result.fileEntryType = fileEntryTypeValue;
    const configPathValue = dataset['configPath'];
    if (configPathValue) result.configPath = configPathValue;
    return result;
};

const readSearchItemDataset = (itemElement: HTMLElement): SearchItemDataset => readSearchResultDataset(itemElement.dataset);

const buildSearchResultDataset = (item: SearchItem): SearchItemDataset => {
    const type = readDatasetText(item.type);
    if (!type) {
        throw new Error('Search result dataset requires a type');
    }
    const id = readDatasetText(item.id);
    if (!id) {
        throw new Error('Search result dataset requires an id');
    }
    const dataset: SearchItemDataset = { type, id };
    const plugin = readDatasetText(item.plugin);
    if (plugin) dataset.plugin = plugin;
    const component = readDatasetText(item.component);
    if (component) dataset.component = component;
    if (item.gpuIndex !== undefined) dataset.gpuIndex = String(item.gpuIndex);
    const identifier = readDatasetText(item.identifier);
    if (identifier) dataset.identifier = identifier;
    const metric = readDatasetText(item.metric);
    if (metric) dataset.metric = metric;
    const filePath = readDatasetText(item.filePath);
    if (filePath) dataset.filePath = filePath;
    const fileEntryType = readDatasetText(item.fileEntryType);
    if (fileEntryType) dataset.fileEntryType = fileEntryType;
    const configPath = readDatasetText(item.configPath);
    if (configPath) dataset.configPath = configPath;
    return dataset;
};

const resolveSearchResultNavigation = (dataset: SearchItemDataset): SearchResultNavigationCommand => {
    const type = readDatasetText(dataset.type);
    if (!type) {
        throw new Error('Search result requires a type');
    }
    const normalized = normalizeSearchCategory(type);

    if (normalized === 'model' || normalized === 'virtual') {
        const id = readDatasetText(dataset.id);
        if (!id) {
            throw new Error('Search model result requires an id');
        }
        return { route: `model/${encodeSegment(id)}` };
    }
    if (normalized === 'plugin') {
        return { route: 'plugins' };
    }
    if (normalized === 'device') {
        const component = readDatasetText(dataset.component);
        if (!component) {
            throw new Error('Search device result requires a component');
        }
        const query: Record<string, string> = { component };
        const gpuIndex = readDatasetText(dataset.gpuIndex);
        const identifier = readDatasetText(dataset.identifier);
        const metric = readDatasetText(dataset.metric);
        if (component === 'gpu' && gpuIndex) query['gpu_index'] = gpuIndex;
        if ((component === 'disk' || component === 'network') && identifier) query['identifier'] = identifier;
        if (metric) query['metric'] = metric;
        return { route: 'hardware', query };
    }
    if (normalized === 'config' || normalized === 'configuration') {
        const tab = readDatasetText(dataset.identifier);
        const configPath = readDatasetText(dataset.configPath);
        if (configPath) {
            return { route: 'settings', query: buildSettingsConfigPathDeepLinkQuery({ tab, configPath }) };
        }
        return tab ? { route: 'settings', query: { tab } } : { route: 'settings' };
    }
    if (normalized === 'help') {
        const section = readDatasetText(dataset.identifier);
        if (!section) {
            throw new Error('Search help result requires an identifier');
        }
        return { route: 'help', query: { section } };
    }
    if (normalized === 'modal') {
        const modal = readDatasetText(dataset.identifier);
        const target = MODAL_SEARCH_TARGETS[modal];
        if (!target) {
            throw new Error('Search modal result requires a supported identifier');
        }
        return target;
    }
    if (normalized === 'power-actions') {
        const action = readDatasetText(dataset.identifier);
        const target = POWER_ACTION_TARGETS[action];
        if (!target) {
            throw new Error('Search power action result requires a supported identifier');
        }
        return target;
    }
    if (normalized === 'page') {
        const id = readDatasetText(dataset.id);
        if (!id) {
            throw new Error('Search page result requires an id');
        }
        return { route: id };
    }
    if (normalized === 'conversation') {
        const id = readDatasetText(dataset.id);
        if (!id) {
            throw new Error('Search conversation result requires an id');
        }
        return { route: `chat/conversation/${encodeSegment(id)}` };
    }
    if (normalized === 'prompt') {
        const id = readDatasetText(dataset.id);
        if (!id) {
            throw new Error('Search prompt result requires an id');
        }
        return { route: 'prompts', query: { prompt: id } };
    }
    if (normalized === 'files') {
        const filePathRaw = readDatasetText(dataset.filePath);
        if (!filePathRaw) {
            throw new Error('Search file result requires a file path');
        }
        const filePath = toVirtualPath(filePathRaw);
        const fileEntryType = readDatasetText(dataset.fileEntryType);
        const directoryPath = parentVirtualPath(filePath);
        const search = basenameVirtualPath(filePath);
        if (fileEntryType === 'file') {
            return {
                route: 'fileExplorer',
                query: buildFileExplorerDeepLinkQuery({
                    directoryPath,
                    highlightPath: filePath,
                    search,
                    previewPath: filePath
                })
            };
        } else if (fileEntryType !== 'directory') {
            throw new Error('Search file result requires a supported file entry type');
        }
        return {
            route: 'fileExplorer',
            query: buildFileExplorerDeepLinkQuery({
                directoryPath,
                highlightPath: filePath,
                search
            })
        };
    }
    throw new Error(`Unsupported search result type "${normalized}"`);
};

export { SEARCH_RESULT_DATASET_ATTRIBUTES, buildSearchResultDataset, readSearchItemDataset, readSearchResultDataset, resolveSearchResultNavigation };
export type { SearchItemDataset, SearchResultDatasetAttribute, SearchResultNavigationCommand };
