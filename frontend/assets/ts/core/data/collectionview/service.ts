/* SoAI - Shared data collection view service [frontend/assets/ts/core/data/collectionview/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { type ClientDataHub, type ResourceOperation, type ResourceSnapshot } from '@core/data/ClientDataHub.ts';
import { requireClientDataHub } from '@core/data/clientdatahub/runtime.ts';
import { createCollectionRuntime, createCollectionRenderer, resolveCollectionTrackBy, resolveRefreshReason } from '@core/data/collectionview/effects.ts';
import type { CollectionCriteria, CollectionRuntime, CollectionRuntimeHost, CollectionItem, CollectionViewHost, CollectionViewOptions, FilterFunction, PreparePresentationFunction, PresentationFingerprintFunction, RefreshContext, SortFunction, TrackByFunction } from '@core/data/collectionview/types.ts';
import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { isArray, isFunction, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';

class CollectionView implements CollectionRuntimeHost {
    resource: string;
    host: CollectionViewHost;
    trackBy: TrackByFunction;
    presentationFingerprint: PresentationFingerprintFunction | null;
    hub: ClientDataHub;
    filterFunctionValue: FilterFunction | null = null;
    sortFunctionValue: SortFunction | null = null;
    allItems: CollectionItem[] = [];
    filteredItems: CollectionItem[] = [];
    itemLookup = new Map<string, CollectionItem>();
    presentationFingerprints = new Map<string, string>();
    authoritativeIds: string[] = [];
    orderedIds: string[] = [];
    refreshHandle: number | null = null;
    pendingRefreshContext: { reason: string } | null = null;
    animationFrame: (callback: FrameRequestCallback) => number;
    cancelAnimationFrame: (handle: number) => void;
    onSnapshot: ((snapshot: ResourceSnapshot) => void) | null;
    preparePresentation: PreparePresentationFunction | null;
    onRefresh: ((context: RefreshContext) => void) | null;
    pendingDirtyIds = new Set<string>();
    renderer: ReturnType<typeof createCollectionRenderer>;
    unsubscribe: () => void;
    collectionRuntime: CollectionRuntime;
    authoritativeRevision = -1;
    hasPresentedSnapshot = false;

    constructor({ resource, host, trackBy, presentationFingerprint, hub, renderItem, loadingLabel, resolveContainer, resolveItemIdentifier, resolveEmptyState, onSnapshot = null, preparePresentation = null, onRefresh = null, onCommit = null }: CollectionViewOptions) {
        if (!isString(resource) || !resource.trim()) throw new Error('CollectionView requires a resource identifier');
        if (!isObject(host)) throw new Error('CollectionView requires a host reference');
        this.resource = resource.trim();
        this.host = host;
        this.trackBy = resolveCollectionTrackBy(trackBy);
        this.presentationFingerprint = isFunction(presentationFingerprint) ? presentationFingerprint : null;
        this.hub = hub ?? requireClientDataHub();
        this.animationFrame = getRequestAnimationFrame();
        this.cancelAnimationFrame = getCancelAnimationFrame();
        this.onSnapshot = isFunction(onSnapshot) ? onSnapshot : null;
        this.preparePresentation = isFunction(preparePresentation) ? preparePresentation : null;
        this.onRefresh = isFunction(onRefresh) ? onRefresh : null;
        this.renderer = createCollectionRenderer({ resource: this.resource, renderItem, loadingLabel, resolveContainer, resolveItemIdentifier, resolveEmptyState, onCommit });
        const snapshotCallback = this.onSnapshot;
        this.unsubscribe = this.hub.subscribe(this.resource, (snapshot): void => {
            this.#syncSnapshot(snapshot);
            snapshotCallback?.(snapshot);
        });
        this.collectionRuntime = createCollectionRuntime(this);
    }

    dispose(): void {
        this.unsubscribe();
        this.renderer.dispose();
        if (this.refreshHandle !== null) this.cancelAnimationFrame(this.refreshHandle);
        this.refreshHandle = null;
        this.pendingRefreshContext = null;
        this.filterFunctionValue = null;
        this.sortFunctionValue = null;
        this.preparePresentation = null;
        this.allItems = [];
        this.filteredItems = [];
        this.orderedIds = [];
        this.authoritativeIds = [];
        this.itemLookup.clear();
        this.presentationFingerprints.clear();
        this.pendingDirtyIds.clear();
    }

    applyCriteria(criteria: CollectionCriteria = {}): CollectionItem[] {
        if (Object.hasOwn(criteria, 'filter')) this.filterFunctionValue = isFunction(criteria.filter) ? criteria.filter : null;
        if (Object.hasOwn(criteria, 'sort')) this.sortFunctionValue = isFunction(criteria.sort) ? criteria.sort : null;
        return this.refresh({ reason: 'criteria', resetScroll: criteria.resetScroll === true });
    }

    refresh(context: { reason?: string; resetScroll?: boolean } = {}): CollectionItem[] {
        const filtered = this.allItems.filter((item) => this.filterFunctionValue === null || this.filterFunctionValue(item));
        if (this.sortFunctionValue !== null) filtered.sort(this.sortFunctionValue);
        const orderedIds: string[] = [];
        const filteredLookup = new Map<string, CollectionItem>();
        for (const item of filtered) {
            const identifier = this.trackBy(item);
            if (identifier === null) throw new Error(`CollectionView ${this.resource} item identity is required`);
            if (filteredLookup.has(identifier)) throw new Error(`CollectionView ${this.resource} item identity is duplicate: ${identifier}`);
            orderedIds.push(identifier);
            filteredLookup.set(identifier, item);
        }
        const reason = resolveRefreshReason(context.reason);
        const preparedDirtyIds = this.preparePresentation?.({ filtered: Object.freeze(filtered.slice()), orderedIds: Object.freeze(orderedIds.slice()), itemLookup: filteredLookup, reason }) ?? [];
        for (const identifier of preparedDirtyIds) {
            if (!filteredLookup.has(identifier)) throw new Error(`CollectionView ${this.resource} presentation preparation returned unknown item identity: ${identifier}`);
            this.pendingDirtyIds.add(identifier);
        }
        const dirtyIds = this.#consumeDirtyIds();
        this.filteredItems = filtered;
        this.orderedIds = orderedIds;
        this.renderer.update({ ids: orderedIds, lookup: filteredLookup, dirtyIds, resetScroll: context.resetScroll === true });
        const refreshContext: RefreshContext = Object.freeze({
            filtered: Object.freeze(filtered.slice()),
            orderedIds: Object.freeze(orderedIds.slice()),
            itemLookup: filteredLookup,
            dirtyIds: Object.freeze(dirtyIds),
            filteredCount: filtered.length,
            totalCount: this.allItems.length,
            reason
        });
        this.onRefresh?.(refreshContext);
        return filtered.slice();
    }

    getCollectionRuntime(): CollectionRuntime {
        return this.collectionRuntime;
    }

    upsertLocal(item: CollectionItem): CollectionItem | null {
        if (!item) return null;
        this.hub.applyLocalOperation(this.resource, { type: 'upsert', item });
        return item;
    }

    removeLocal(id: string): boolean {
        if (isNullOrUndefined(id)) return false;
        this.hub.applyLocalOperation(this.resource, { type: 'remove', id });
        return true;
    }

    replaceLocal(items: CollectionItem[]): CollectionItem[] {
        const list = isArray(items) ? items : [];
        this.hub.applyLocalOperation(this.resource, { type: 'replace', items: list });
        return list;
    }

    applyOperations(operations: ResourceOperation | ResourceOperation[]): void {
        for (const operation of isArray(operations) ? operations : [operations]) this.hub.applyLocalOperation(this.resource, operation);
    }

    markDirty(ids: string[] = []): void {
        if (ids.length === 0) return;
        for (const identifier of ids) this.pendingDirtyIds.add(identifier);
        this.#scheduleRefresh({ reason: 'presentation-dirty' });
    }

    async revealItem(id: string): Promise<boolean> {
        return await this.renderer.reveal(id);
    }

    rebuildForViewMode(): void {
        this.refresh({ reason: 'view-mode' });
    }

    prepareForViewModeChange(): void {
        this.renderer.prepareForViewModeChange();
    }

    flushPendingRefresh(): void {
        if (this.refreshHandle === null) {
            if (this.pendingRefreshContext) throw new Error(`CollectionView ${this.resource} pending refresh requires a scheduled frame`);
            return;
        }
        this.cancelAnimationFrame(this.refreshHandle);
        this.refreshHandle = null;
        this.#runPendingRefresh();
    }

    async awaitInitialCommit(signal: AbortSignal | null): Promise<boolean> {
        return await this.renderer.awaitInitialCommit(signal);
    }

    #syncSnapshot(snapshot: ResourceSnapshot): void {
        const authoritativeChanged = snapshot.authoritativeRevision !== this.authoritativeRevision;
        const hasItemChanges = snapshot.diff.added.length > 0 || snapshot.diff.updated.length > 0 || snapshot.diff.removed.length > 0;
        if (!snapshot.hasAuthoritativeSnapshot && !hasItemChanges) return;
        if (!authoritativeChanged && !hasItemChanges) return;
        const nextItems = isArray(snapshot.items) ? snapshot.items.slice() : [];
        const nextLookup = new Map<string, CollectionItem>();
        const nextFingerprints = new Map<string, string>();
        const nextAuthoritativeIds: string[] = [];
        const dirtyIds: string[] = [];
        for (const item of nextItems) {
            const identifier = this.trackBy(item);
            if (identifier === null) throw new Error(`CollectionView ${this.resource} item identity is required`);
            if (nextLookup.has(identifier)) throw new Error(`CollectionView ${this.resource} item identity is duplicate: ${identifier}`);
            nextLookup.set(identifier, item);
            nextAuthoritativeIds.push(identifier);
            if (this.presentationFingerprint !== null) {
                const fingerprint = this.presentationFingerprint(item);
                if (!isString(fingerprint)) throw new Error(`CollectionView ${this.resource} presentation fingerprint must be a string`);
                nextFingerprints.set(identifier, fingerprint);
                if (this.presentationFingerprints.get(identifier) !== fingerprint) dirtyIds.push(identifier);
            }
        }
        const identitiesChanged = nextAuthoritativeIds.length !== this.authoritativeIds.length || nextAuthoritativeIds.some((identifier, index) => this.authoritativeIds[index] !== identifier);
        this.authoritativeRevision = snapshot.authoritativeRevision;
        this.allItems = nextItems;
        this.itemLookup = nextLookup;
        this.authoritativeIds = nextAuthoritativeIds;
        this.presentationFingerprints = nextFingerprints;
        const presentationChanged = !this.hasPresentedSnapshot || identitiesChanged || dirtyIds.length > 0;
        this.hasPresentedSnapshot = true;
        if (this.presentationFingerprint === null) {
            for (const identifier of snapshot.diff.updated) this.pendingDirtyIds.add(identifier);
        } else {
            for (const identifier of dirtyIds) this.pendingDirtyIds.add(identifier);
        }
        if (presentationChanged || this.presentationFingerprint === null) {
            this.#scheduleRefresh({ reason: snapshot.authoritativeReason ?? 'collection-update' });
            return;
        }
        this.#synchronizeEquivalentSnapshot();
    }

    #synchronizeEquivalentSnapshot(): void {
        if (this.refreshHandle !== null) return;
        const filteredLookup = new Map<string, CollectionItem>();
        const filteredItems: CollectionItem[] = [];
        for (const identifier of this.orderedIds) {
            const item = this.itemLookup.get(identifier);
            if (item === undefined) throw new Error(`CollectionView ${this.resource} filtered identity is missing: ${identifier}`);
            filteredLookup.set(identifier, item);
            filteredItems.push(item);
        }
        this.filteredItems = filteredItems;
        this.renderer.update({ ids: this.orderedIds, lookup: filteredLookup, dirtyIds: [], synchronizeLookupOnly: true });
    }

    #consumeDirtyIds(): string[] {
        const dirtyIds = Array.from(this.pendingDirtyIds);
        this.pendingDirtyIds.clear();
        return dirtyIds;
    }

    #scheduleRefresh(context: { reason: string }): void {
        this.pendingRefreshContext = context;
        if (this.refreshHandle !== null) return;
        this.refreshHandle = this.animationFrame(() => {
            this.refreshHandle = null;
            this.#runPendingRefresh();
        });
    }

    #runPendingRefresh(): void {
        const pending = this.pendingRefreshContext;
        this.pendingRefreshContext = null;
        if (!pending) throw new Error(`CollectionView ${this.resource} refresh handle requires pending context`);
        this.refresh(pending);
    }
}

export { CollectionView };
export type { CollectionCriteria, CollectionRuntime, CollectionItem, CollectionViewOptions, FilterFunction, RefreshContext, SortFunction, TrackByFunction };
