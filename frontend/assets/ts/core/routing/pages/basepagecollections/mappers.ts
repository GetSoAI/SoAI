/* SoAI - Shared frontend routing pages base page collections mapping [frontend/assets/ts/core/routing/pages/basepagecollections/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { matchesCollectionSearchFields, normalizeCollectionSearchQuery } from '@core/collectionpage/search.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { normalizeResourceItem } from '@core/data/clientdatahub/guards.ts';
import type { ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import { isArray, isBigInt, isFiniteNumber, isFunction, isNode, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import type { CollectionConfigurationOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { PageCollectionBehavior } from '@core/routing/pages/basepagecollections/contracts.ts';

const createRenderItemFactory = (behavior: PageCollectionBehavior, config: CollectionConfigurationOptions): ((item: ResourceItem, context?: ResourceIncomingValue) => HTMLElement) => {
    const configuredRenderItem = config.renderItem;
    if (isFunction(configuredRenderItem)) {
        return (item: ResourceItem, context?: ResourceIncomingValue): HTMLElement => {
            const rendered = configuredRenderItem(item, context);
            if (rendered instanceof HTMLElement) {
                return rendered;
            }
            if (isNode(rendered)) {
                throw err('renderItemCard must return an HTMLElement');
            }
            throw err('renderItem must return an HTMLElement');
        };
    }

    const renderItemCard = behavior.renderItemCard;
    if (isFunction(renderItemCard)) {
        return (item: ResourceItem, context?: ResourceIncomingValue): HTMLElement => {
            const rendered = renderItemCard(item, context);
            if (rendered instanceof HTMLElement) {
                return rendered;
            }
            if (isNode(rendered)) {
                throw err('renderItemCard must return an HTMLElement');
            }
            throw err('renderItemCard must return an HTMLElement');
        };
    }

    const renderItem = behavior.renderItem;
    if (isFunction(renderItem)) {
        return (item: ResourceItem, context?: ResourceIncomingValue): HTMLElement => {
            const rendered = renderItem(item, context);
            if (rendered instanceof HTMLElement) {
                return rendered;
            }
            if (isNode(rendered)) {
                throw err('renderItem must return an HTMLElement');
            }
            throw err('renderItem must return an HTMLElement');
        };
    }

    throw err('renderItem renderer is required');
};

const createCollectionNormalizer = (config: CollectionConfigurationOptions): ((item: ResourceIncomingValue) => ResourceItem) => {
    return (item: ResourceIncomingValue): ResourceItem => {
        const normalizer = config.collectionOptions?.normalize;
        if (!isFunction(normalizer)) {
            return normalizeResourceItem(item, 'Collection item');
        }
        const normalized = normalizer(item);
        return normalizeResourceItem(normalized, 'Collection normalize() result');
    };
};

const getCollectionFilter = (behavior: PageCollectionBehavior): ((item: ResourceItem) => boolean) => {
    const query = normalizeCollectionSearchQuery(behavior.searchQuery || '');
    const provider = behavior.filterProvider;
    const status = behavior.filterStatus;
    if (!isString(provider) || !isString(status)) {
        throw err('Filter provider/status missing');
    }
    const rawGetItemSearchFields = behavior.getItemSearchFields;
    const rawApplyCustomFilters = behavior.applyCustomFilters;
    const getItemSearchFieldsResolver = isFunction(rawGetItemSearchFields) ? (item: ResourceItem): (string | undefined)[] => rawGetItemSearchFields(item) : null;
    const applyCustomFiltersResolver = isFunction(rawApplyCustomFilters) ? (item: ResourceItem, context: { filterProvider: string; filterStatus: string }): boolean => rawApplyCustomFilters(item, context) : null;
    return (item: ResourceItem): boolean => {
        if (!item || !isObject(item)) {
            return false;
        }
        if (query) {
            if (!getItemSearchFieldsResolver) {
                throw err('getItemSearchFields must be implemented when search is enabled');
            }
            const fields = getItemSearchFieldsResolver(item);
            if (!isArray(fields)) {
                throw err('getItemSearchFields must return an array');
            }
            if (!matchesCollectionSearchFields(fields, query)) {
                return false;
            }
        }
        return applyCustomFiltersResolver ? Boolean(applyCustomFiltersResolver(item, { filterProvider: provider, filterStatus: status })) : true;
    };
};

const getCollectionSorter = (behavior: PageCollectionBehavior): ((firstValue: ResourceItem, secondValue: ResourceItem) => number) | null => {
    const field = behavior.sortBy;
    if (!field) {
        throw err('SortBy missing');
    }
    if (field === 'none') return null;
    const direction = behavior.sortOrder === 'asc' ? 1 : -1;
    const rawGetSortValue = behavior.getSortValue;
    const getSortValueResolver = isFunction(rawGetSortValue) ? (item: ResourceItem) => rawGetSortValue(item, field) : (item: ResourceItem) => item[field];
    const normalizeSortable = (value: ResourceIncomingValue | null | undefined): { n: boolean; v: number | string } => {
        const bigintValue = isBigInt(value);
        return {
            n: isFiniteNumber(value) || bigintValue,
            v: bigintValue ? Number(value) : isFiniteNumber(value) ? value : (isNullOrUndefined(value) ? '' : String(value)).toLowerCase()
        };
    };
    return (left: ResourceItem, right: ResourceItem): number => {
        const leftNormalized = normalizeSortable(getSortValueResolver(left));
        const rightNormalized = normalizeSortable(getSortValueResolver(right));
        return (leftNormalized.n && rightNormalized.n ? (leftNormalized.v === rightNormalized.v ? 0 : leftNormalized.v > rightNormalized.v ? 1 : -1) : String(leftNormalized.v).localeCompare(String(rightNormalized.v), getLanguageService().getLocale())) * direction;
    };
};

export { createRenderItemFactory, createCollectionNormalizer, getCollectionFilter, getCollectionSorter };
