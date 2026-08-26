/* SoAI - Shared plugins model repository contract [frontend/assets/ts/core/plugins/modelRepositoryContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { PluginModelRepository, PluginModelRepositoryCatalogEntry, PluginModelRepositoryRecord } from '@core/types/pluginTypes.ts';
import { readOptionalStringValue } from '@core/types/payloadValueReaders.ts';

const parseOptionalArray = (value: JsonValue | undefined, label: string): JsonValue[] | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!isJsonArray(value)) throw new TypeError(`${label} must be an array when provided`);
    return [...value];
};

const parseCatalogEntry = (value: JsonValue, index: number): PluginModelRepositoryCatalogEntry => {
    if (!isJsonObject(value)) throw new TypeError(`plugins.collection model_repository.catalog[${String(index)}] must be an object`);
    const entry: PluginModelRepositoryCatalogEntry = {};
    const id = readOptionalStringValue(value['id'], `plugins.collection model_repository.catalog[${String(index)}].id`);
    const name = readOptionalStringValue(value['name'], `plugins.collection model_repository.catalog[${String(index)}].name`);
    const slug = readOptionalStringValue(value['slug'], `plugins.collection model_repository.catalog[${String(index)}].slug`);
    const displayName = readOptionalStringValue(value['display_name'], `plugins.collection model_repository.catalog[${String(index)}].display_name`);
    const repositoryUrl = readOptionalStringValue(value['repository_url'], `plugins.collection model_repository.catalog[${String(index)}].repository_url`);
    const aliases = parseOptionalArray(value['aliases'], `plugins.collection model_repository.catalog[${String(index)}].aliases`);
    const tags = parseOptionalArray(value['tags'], `plugins.collection model_repository.catalog[${String(index)}].tags`);
    if (id !== undefined) entry.id = id;
    if (name !== undefined) entry.name = name;
    if (slug !== undefined) entry.slug = slug;
    if (displayName !== undefined) entry.displayName = displayName;
    if (repositoryUrl !== undefined) entry.repositoryUrl = repositoryUrl;
    if (aliases !== undefined) entry.aliases = aliases;
    if (tags !== undefined) entry.tags = tags;
    return entry;
};

const parseModelRepositoryRecord = (value: JsonValue): PluginModelRepositoryRecord => {
    if (!isJsonObject(value)) throw new TypeError('plugins.collection model_repository must be a string, object, or null');
    const repository: PluginModelRepositoryRecord = {};
    const catalogValue = value['catalog'];
    if (catalogValue !== undefined && catalogValue !== null) {
        if (!isJsonArray(catalogValue)) throw new TypeError('plugins.collection model_repository.catalog must be an array when provided');
        repository.catalog = catalogValue.map(parseCatalogEntry);
    }
    const repositoryUrl = readOptionalStringValue(value['repository_url'], 'plugins.collection model_repository.repository_url');
    const url = readOptionalStringValue(value['url'], 'plugins.collection model_repository.url');
    const baseUrl = readOptionalStringValue(value['base_url'], 'plugins.collection model_repository.base_url');
    const link = readOptionalStringValue(value['link'], 'plugins.collection model_repository.link');
    const href = readOptionalStringValue(value['href'], 'plugins.collection model_repository.href');
    const displayName = readOptionalStringValue(value['display_name'], 'plugins.collection model_repository.display_name');
    const name = readOptionalStringValue(value['name'], 'plugins.collection model_repository.name');
    const tags = parseOptionalArray(value['tags'], 'plugins.collection model_repository.tags');
    if (repositoryUrl !== undefined) repository.repositoryUrl = repositoryUrl;
    if (url !== undefined) repository.url = url;
    if (baseUrl !== undefined) repository.baseUrl = baseUrl;
    if (link !== undefined) repository.link = link;
    if (href !== undefined) repository.href = href;
    if (displayName !== undefined) repository.displayName = displayName;
    if (name !== undefined) repository.name = name;
    if (tags !== undefined) repository.tags = tags;
    return repository;
};

const parsePluginModelRepository = (value: JsonValue): PluginModelRepository => {
    if (value === null) return null;
    if (typeof value === 'string') return value;
    return parseModelRepositoryRecord(value);
};

const resolvePluginModelRepositoryUrl = (repository: PluginModelRepository | undefined): string | null => {
    if (typeof repository === 'string') return repository;
    if (!repository) return null;
    return repository.repositoryUrl ?? repository.url ?? repository.baseUrl ?? repository.link ?? repository.href ?? null;
};

export { parsePluginModelRepository, resolvePluginModelRepositoryUrl };
