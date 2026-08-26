/* SoAI - Frontend card page controller composition [frontend/assets/ts/core/routing/pages/collections/cardgridpage/cardPageController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { collectionCache } from '@core/collectionCache.ts';
import { i18n } from '@core/i18n/index.ts';
import { loadingState } from '@core/loadingState.ts';
import { isArray, isElementNode, isFunction, isString } from '@core/typeGuards.ts';
import type { CardPageConfig, CardPageController, CardPageHost, RenderOptions } from '@core/routing/pages/collections/cardgridpage/contracts.ts';
import { applyEmptyStates, resolveDataValue } from '@core/routing/pages/collections/cardgridpage/domData.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
export function createCardPageController(host: CardPageHost, config: CardPageConfig): CardPageController {
    if (!host) throw new Error('Card page controller requires a host');
    const { dataKey, getItemId, resolveCurrentItem, itemLabel = 'Item', collectionName = 'collection', gridSelector = null, emptyStates = null, cacheKey = null, loadingText = null } = config;
    if (!isString(dataKey) || !dataKey.trim()) throw new Error('Card page controller requires dataKey');
    if (!isFunction(getItemId)) throw new Error('Card page controller requires getItemId');
    const normalizedKey = dataKey.trim();
    const label = itemLabel;
    const collectionLabel = collectionName;
    const defaultEmptyStates = isArray(emptyStates) ? emptyStates : null;
    let registry = new WeakMap<Element, ResourceIncomingValue | null>();
    const cardIndex = new Map<string, ResourceIncomingValue | null>();
    let dataInitialized = false;
    let initialEmptyStateApplied = false;
    let loadingActive = true;
    const getLoadingText = (): string => {
        if (isString(loadingText) && loadingText.trim()) {
            return loadingText.trim();
        }
        return i18n.t('common.loading');
    };
    const getGridElement = (): Element | null => {
        return gridSelector ? host.optionalUI(gridSelector) : null;
    };
    const showLoading = (): void => {
        const grid = getGridElement();
        if (!grid) return;
        loadingActive = true;
        host.toggleHidden(grid, false);
        loadingState.setElementState(grid, true, getLoadingText(), { withSpinner: false });
        if (defaultEmptyStates) {
            for (const state of defaultEmptyStates) {
                const target = state?.element || (state?.selector ? host.optionalUI(state.selector) : null);
                if (target) host.toggleHidden(target, true);
            }
        }
    };
    const hideLoading = (): void => {
        const grid = getGridElement();
        if (grid) {
            loadingState.setElementState(grid, false, getLoadingText(), { withSpinner: false });
        }
        loadingActive = false;
    };
    const isLoadingActive = (): boolean => loadingActive;
    const setDataInitialized = (): void => {
        dataInitialized = true;
        initialEmptyStateApplied = false;
        hideLoading();
    };
    const syncIndex = (items: (ResourceIncomingValue | null)[]): void => {
        cardIndex.clear();
        if (!isArray(items)) return;
        for (const item of items) {
            const id = getItemId(item);
            if (id) cardIndex.set(id, item);
        }
    };
    const getItemFromCard = (card: Element): ResourceIncomingValue | null | undefined => {
        if (!isElementNode(card)) throw new Error(`${label} card element required`);
        const cached = registry.get(card);
        if (card.isConnected && cached && !resolveCurrentItem) return cached;
        const id = resolveDataValue(host, card, normalizedKey);
        if (!id) throw new Error(`${label} card missing data-${normalizedKey} attribute`);
        if (!cardIndex.has(id)) throw new Error(`${label} "${id}" not registered in ${collectionLabel} collection`);
        const resolved = resolveCurrentItem ? resolveCurrentItem(id) : cardIndex.get(id);
        if (resolved === undefined) throw new Error(`${label} "${id}" resolved to an invalid ${collectionLabel} item`);
        if (card.isConnected) registry.set(card, resolved);
        return resolved;
    };
    const renderCollection = ({ filteredItems = [], allItems = [], emptyStates: stateOverride = null }: RenderOptions = {}): void => {
        const filtered = isArray(filteredItems) ? filteredItems : [];
        const all = isArray(allItems) ? allItems : [];
        syncIndex(filtered);
        if (dataInitialized) {
            const cachedHasItems = cacheKey ? collectionCache.hasItemsCached(cacheKey) : null;
            const shouldSuppressEmptyState = !initialEmptyStateApplied && cachedHasItems === true && all.length === 0;
            if (!shouldSuppressEmptyState) {
                applyEmptyStates(host, stateOverride ?? defaultEmptyStates, filtered, all);
            }
            initialEmptyStateApplied = true;
            if (cacheKey) {
                collectionCache.set(cacheKey, all.length > 0);
            }
        }
        host.flushDOMUpdates();
    };
    const dispose = (): void => {
        cardIndex.clear();
        registry = new WeakMap();
    };
    return {
        cardIndex,
        getItemFromCard,
        renderCollection,
        syncIndex,
        setDataInitialized,
        showLoading,
        hideLoading,
        isLoading: isLoadingActive,
        dispose
    };
}
export type { CardPageConfig, CardPageController, CardPageHost };
