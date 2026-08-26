/* SoAI - Shared routing base page collections effects [frontend/assets/ts/core/routing/pages/basepagecollections/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { CollectionView, type CollectionViewOptions } from '@core/data/collectionview/service.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import type { ResourceItem } from '@core/data/ClientDataHub.ts';
import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { normalizeItemId } from '@core/routing/pages/basepagecore/mappers.ts';
import type { BasePageCollectionsState } from '@core/routing/pages/basepagecollections/state.ts';
import { isFunction, isNullOrUndefined } from '@core/typeGuards.ts';
import type { CollectionConfigurationOptions, EnsureCollectionStreamOptions, ReapplyCollectionOptions } from '@core/routing/pages/pagetypes/public.ts';
import { createRenderItemFactory, getCollectionFilter, getCollectionSorter } from '@core/routing/pages/basepagecollections/mappers.ts';
import { disposeCollectionView, getCollectionRuntime } from '@core/routing/pages/basepagecollections/dom.ts';
import type { PageCollectionBehavior, PageCollectionsDependencies } from '@core/routing/pages/basepagecollections/contracts.ts';
import { getCollectionKey } from '@core/routing/pages/basepagecollections/actions.ts';

const initializeStandardCollection = (dependencies: PageCollectionsDependencies, behavior: PageCollectionBehavior, state: BasePageCollectionsState, config: CollectionConfigurationOptions): void => {
    if (!config.collectionKey) {
        throw err('Collection key required');
    }
    const collectionId = config.collectionKey.trim();
    state.collectionConfig = {
        ...state.collectionConfig,
        ...config,
        collectionKey: collectionId,
        gridId: config.gridId || `${dependencies.pageId}-grid`,
        emptyStateId: config.emptyStateId || `${dependencies.pageId}-empty`
    };
    const previousCollectionView = state.collectionView;
    runCleanup(previousCollectionView ? () => disposeCollectionView(previousCollectionView) : null, (runtimeError) => {
        errorHandler.warn('BasePageCollections', 'Collection view cleanup failed', runtimeError);
    });
    const renderItem = createRenderItemFactory(behavior, config);
    const normalizeId = config.collectionOptions?.normalizeId;
    const presentationFingerprint = config.collectionOptions?.fingerprint;
    if (!isFunction(config.resolveItemIdentifier)) {
        throw err('Collection item identifier resolver required');
    }
    if (!isFunction(config.loadingLabel)) {
        throw err('Collection loading label resolver required');
    }
    const collectionOptions: CollectionViewOptions = {
        resource: collectionId,
        host: behavior,
        trackBy: isFunction(normalizeId)
            ? (item: ResourceItem): string | null => {
                  const identifier = normalizeId(item);
                  return isNullOrUndefined(identifier) ? null : String(identifier);
              }
            : normalizeItemId,
        presentationFingerprint: isFunction(presentationFingerprint) ? presentationFingerprint : undefined,
        renderItem: (item: ResourceItem, _id: string): HTMLElement => renderItem(item),
        loadingLabel: config.loadingLabel,
        resolveItemIdentifier: config.resolveItemIdentifier,
        resolveContainer: () => {
            if (config.resolveContainer) {
                return config.resolveContainer();
            }
            const configRef = state.collectionConfig;
            if (!configRef || !configRef.gridId) return null;
            const element = dependencies.pageDom.get(configRef.gridId);
            return element instanceof HTMLElement ? element : null;
        },
        onSnapshot: (snapshot) => behavior.onCollectionSnapshot?.(snapshot) ?? null,
        preparePresentation: behavior.prepareCollectionPresentation,
        onRefresh: (snapshot) => behavior.onCollectionRefresh?.(snapshot),
        onCommit: (context) => behavior.onCollectionCommit?.(context)
    };
    state.collectionView = new CollectionView(collectionOptions);
    state.collection = state.collectionView.getCollectionRuntime();
};

const ensureCollectionStream = async (dependencies: PageCollectionsDependencies, state: BasePageCollectionsState, options: EnsureCollectionStreamOptions = {}): Promise<string> => {
    const collectionKey = options.collectionKey ? String(options.collectionKey).trim() : getCollectionKey(state);
    const resources = options.streamManager ?? dependencies.streaming.runtime().resources;
    await dependencies.streaming.ensureReady(resources, options.allowDiscovery !== false, options.signal);
    await resources.ensureResourceStarted(collectionKey, { signal: options.signal });
    return collectionKey;
};

const toggleEmptyState = (dependencies: PageCollectionsDependencies, state: BasePageCollectionsState, showEmpty: boolean): void => {
    const config = state.collectionConfig;
    if (!config?.emptyStateId || !config.gridId) return;
    const emptyElement = dependencies.pageDom.get(config.emptyStateId);
    const gridElement = dependencies.pageDom.get(config.gridId);
    if (!emptyElement || !gridElement) return;
    dependencies.pageDom.toggleClass(emptyElement, CSS_CLASSES.HIDDEN, !showEmpty);
    dependencies.pageDom.toggleClass(gridElement, CSS_CLASSES.HIDDEN, showEmpty);
    dependencies.pageDom.flush();
};

const reapplyCollection = (dependencies: PageCollectionsDependencies, behavior: PageCollectionBehavior, state: BasePageCollectionsState, { shouldRender = true, updateStats = false, updateFilters = false, resetScroll = false }: ReapplyCollectionOptions = {}): void => {
    const collectionRuntime = getCollectionRuntime(state);
    if (!collectionRuntime?.apply) {
        if (dependencies.pageLifecycle.isDestroyed) {
            return;
        }
        throw err('Collection unavailable');
    }
    if (shouldRender) collectionRuntime.apply({ filter: getCollectionFilter(behavior), sort: getCollectionSorter(behavior), resetScroll });
    if (updateStats) {
        const updateStatsFunctionValue = behavior.updateStats;
        if (isFunction(updateStatsFunctionValue)) {
            updateStatsFunctionValue();
        }
    }
    if (updateFilters) {
        const updateFiltersFunctionValue = behavior.updateFilters;
        if (isFunction(updateFiltersFunctionValue)) {
            updateFiltersFunctionValue();
        }
    }
};

export { initializeStandardCollection, ensureCollectionStream, reapplyCollection, toggleEmptyState };
