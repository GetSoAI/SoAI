/* SoAI - Bounded contiguous collection renderer [frontend/assets/ts/core/data/boundedcollectionrenderer/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { COLLECTION_BUILD_FRAME_BUDGET_MS, COLLECTION_PAGE_SIZE, COLLECTION_RETAINED_PAGE_COUNT, createBackwardRange, createCompleteRange, createForwardRange, createInitialRange, createTargetRange, reconcileRangeAfterDataChange, validateCollectionSequence, type CollectionRange } from '@core/data/boundedcollectionrenderer/range.ts';
import { CollectionCommitAwaiter } from '@core/data/boundedcollectionrenderer/commitAwaiter.ts';
import { captureViewportAnchor, commitPlannedNodes, createEdgeLoader, createPlannedNode, indexExistingCollectionNodes, restoreKeyedViewportAnchor, restoreViewportAnchor } from '@core/data/boundedcollectionrenderer/transaction.ts';
import type { BoundedCollectionCommitContext, BoundedCollectionRendererOptions, BoundedCollectionUpdate, CollectionBuild, CollectionEdge, CollectionSequenceState, CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/types.ts';
import { CollectionViewportCoordinator } from '@core/data/boundedcollectionrenderer/viewportCoordinator.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { requirePerformanceNow } from '@core/environment/public.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { canSynchronizeCollectionLookup } from '@core/data/boundedcollectionrenderer/updatePolicy.ts';

class BoundedCollectionRenderer<TItem> {
    readonly #options: BoundedCollectionRendererOptions<TItem>;
    readonly #resources = new ResourceTracker();
    readonly #performanceNow = requirePerformanceNow();
    readonly #viewport = new CollectionViewportCoordinator({ onEdge: (edge) => this.#requestEdge(edge), onUnderfill: () => this.#requestUnderfill(), onContainerReady: () => this.#resumeBuild() });
    readonly #retiredContainers = new Set<HTMLElement>();
    #generation = 0;
    #ids: readonly string[] = [];
    #lookup: ReadonlyMap<string, TItem> = new Map();
    #committedRange: CollectionRange = { start: 0, end: 0 };
    #activeBuild: CollectionBuild<TItem> | null = null;
    #queuedEdge: CollectionEdge | null = null;
    #buildFrame: number | null = null;
    #disposed = false;
    #hasCommitted = false;
    readonly #commitAwaiter = new CollectionCommitAwaiter();
    #revealResolver: ((revealed: boolean) => void) | null = null;
    #revealGeneration: number | null = null;
    #layoutInvariantReported = false;
    #preparedViewModeAnchor: CollectionViewportAnchor | null = null;
    #viewModeAnchorPrepared = false;

    constructor(options: BoundedCollectionRendererOptions<TItem>) {
        this.#options = options;
    }

    update(input: BoundedCollectionUpdate<TItem>): void {
        if (this.#disposed) return;
        const identifiers = validateCollectionSequence(input.ids, input.lookup);
        if (canSynchronizeCollectionLookup(input, identifiers, this.#ids, this.#activeBuild, this.#hasCommitted, this.#revealResolver !== null, this.#viewModeAnchorPrepared, this.#viewport.container, this.#options.resolveContainer())) {
            this.#lookup = input.lookup;
            if (this.#activeBuild !== null) this.#activeBuild.lookup = input.lookup;
            return;
        }
        const previousIds = this.#activeBuild?.previousIds ?? this.#ids;
        const previousLookup = this.#activeBuild?.previousLookup ?? this.#lookup;
        const previousRange = this.#committedRange;
        const requestedViewportAnchor = input.restoreViewportAnchor ?? null;
        const restorePreparedViewModeAnchor = this.#viewModeAnchorPrepared || requestedViewportAnchor !== null;
        const viewportAnchor = requestedViewportAnchor ?? (this.#viewModeAnchorPrepared ? this.#preparedViewModeAnchor : this.#viewport.resolveFirstVisibleAnchor());
        this.#preparedViewModeAnchor = null;
        this.#viewModeAnchorPrepared = false;
        const anchorId = viewportAnchor?.identifier ?? null;
        const rendersAllItems = this.#options.renderAllItems === true;
        const isAppendOnly = !rendersAllItems && previousIds.length > 0 && identifiers.length > previousIds.length && previousIds.every((identifier, index) => identifiers[index] === identifier);
        const extendVisibleEnd = isAppendOnly && previousRange.end === previousIds.length && this.#viewport.isAtEnd();
        this.#supersede();
        this.#ids = identifiers;
        this.#lookup = input.lookup;
        const anchorIndex = rendersAllItems || anchorId === null ? -1 : identifiers.indexOf(anchorId);
        const resetScroll = input.resetScroll === true || !this.#hasCommitted;
        let range = rendersAllItems ? createCompleteRange(identifiers.length) : requestedViewportAnchor !== null && anchorIndex >= 0 ? (requestedViewportAnchor.atStart ? createInitialRange(identifiers.length) : createTargetRange(anchorIndex, identifiers.length)) : resetScroll ? createInitialRange(identifiers.length) : reconcileRangeAfterDataChange(previousRange, identifiers.length, anchorIndex >= 0 ? anchorIndex : null);
        if (!rendersAllItems && extendVisibleEnd) range = createForwardRange(range, identifiers.length);
        const dirtyIds = new Set(input.dirtyIds ?? []);
        this.#layoutInvariantReported = false;
        if (!this.#scheduleBuild(range, dirtyIds, null, resetScroll, null, viewportAnchor, { ids: previousIds, lookup: previousLookup }, restorePreparedViewModeAnchor)) {
            if (!this.#hasCommitted) this.#commitAwaiter.settle(false);
            this.#report(new Error('Collection rendering surface is unavailable'));
        }
    }

    async reveal(identifier: string): Promise<boolean> {
        if (this.#disposed) return false;
        const targetIndex = this.#ids.indexOf(identifier);
        if (targetIndex < 0) return false;
        this.#supersede();
        const generation = this.#generation;
        const result = new Promise<boolean>((resolve) => {
            this.#revealResolver = resolve;
            this.#revealGeneration = generation;
        });
        const range = this.#options.renderAllItems === true ? createCompleteRange(this.#ids.length) : createTargetRange(targetIndex, this.#ids.length);
        if (!this.#scheduleBuild(range, new Set(), null, false, identifier, null, { ids: this.#ids, lookup: this.#lookup }, false)) this.#settleReveal(false);
        return result;
    }

    prepareForViewModeChange(): void {
        if (this.#disposed) return;
        this.#preparedViewModeAnchor = this.#viewport.resolveFirstVisibleAnchor();
        this.#viewModeAnchorPrepared = true;
    }

    captureViewportAnchor(): CollectionViewportAnchor | null {
        return this.#disposed ? null : this.#viewport.resolveFirstVisibleAnchor();
    }

    async awaitInitialCommit(signal: AbortSignal | null = null): Promise<boolean> {
        if (this.#hasCommitted) return true;
        if (this.#disposed || signal?.aborted === true) return false;
        return await this.#commitAwaiter.wait(signal);
    }

    suspendSurface(): void {
        if (this.#disposed) return;
        const activeBuild = this.#activeBuild;
        this.#supersede();
        this.#ids = activeBuild?.previousIds ?? this.#ids;
        this.#lookup = activeBuild?.previousLookup ?? this.#lookup;
        this.#viewport.suspendSurface();
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#supersede();
        this.#viewport.dispose();
        this.#resources.cleanup();
        this.#ids = [];
        this.#lookup = new Map();
        this.#retiredContainers.clear();
        this.#preparedViewModeAnchor = null;
        this.#viewModeAnchorPrepared = false;
        this.#commitAwaiter.settle(false);
    }

    #scheduleBuild(range: CollectionRange, dirtyIds: ReadonlySet<string>, edge: CollectionEdge | null, resetScroll: boolean, revealId: string | null, viewportAnchor: CollectionViewportAnchor | null, previousState: CollectionSequenceState<TItem>, restorePreparedViewModeAnchor: boolean): boolean {
        const container = this.#options.resolveContainer();
        if (container === null) return false;
        const retiredContainer = this.#viewport.attach(container);
        if (retiredContainer !== null) this.#retiredContainers.add(retiredContainer);
        const build: CollectionBuild<TItem> = { generation: this.#generation, container, ids: this.#ids, lookup: this.#lookup, range, dirtyIds, existingNodes: indexExistingCollectionNodes(container), plannedNodes: [], enteringElements: [], cursor: range.start, loader: null, edge, resetScroll, revealId, modeAnchor: restorePreparedViewModeAnchor || retiredContainer !== null ? viewportAnchor : null, previousIds: previousState.ids, previousLookup: previousState.lookup };
        this.#activeBuild = build;
        this.#queueBuildFrame();
        return true;
    }

    #queueBuildFrame(): void {
        if (this.#buildFrame !== null) return;
        this.#buildFrame = this.#resources.requestAnimationFrame(() => {
            this.#buildFrame = null;
            this.#runBuildSlice();
        });
    }

    #resumeBuild(): void {
        if (this.#activeBuild !== null) this.#queueBuildFrame();
    }

    #runBuildSlice(): void {
        const build = this.#activeBuild;
        if (!this.#isCurrentBuild(build)) return;
        try {
            if (build.edge !== null && build.loader === null) {
                const anchor = build.edge === 'backward' ? captureViewportAnchor(build.container) : null;
                build.loader = createEdgeLoader(build.container, build.edge, this.#options.loadingLabel());
                if (build.edge === 'backward') build.container.prepend(build.loader);
                else build.container.append(build.loader);
                if (anchor !== null) restoreViewportAnchor(build.container, anchor);
            }
            if (build.cursor >= build.range.end) {
                this.#commit(build);
                return;
            }
            const startedAt = this.#performanceNow();
            do {
                const requiredTagName = build.container instanceof HTMLTableSectionElement ? 'TR' : null;
                build.plannedNodes.push(createPlannedNode(build, build.cursor, this.#options.renderItem, this.#options.resolveItemIdentifier, requiredTagName));
                build.cursor += 1;
                if (!this.#isCurrentBuild(build)) return;
            } while (build.cursor < build.range.end && this.#performanceNow() - startedAt < COLLECTION_BUILD_FRAME_BUDGET_MS);
            if (build.cursor < build.range.end) {
                this.#queueBuildFrame();
                return;
            }
            this.#commit(build);
        } catch (error) {
            this.#failBuild(build, ensureError(error));
        }
    }

    #commit(build: CollectionBuild<TItem>): void {
        if (!this.#isCurrentBuild(build)) return;
        let commitFailure: Error | null = null;
        try {
            commitPlannedNodes(build);
        } catch (error) {
            commitFailure = ensureError(error);
        }
        if (commitFailure !== null) {
            this.#failBuild(build, commitFailure);
            return;
        }
        build.loader = null;
        if (build.resetScroll) this.#viewport.resetScroll();
        if (build.modeAnchor !== null) restoreKeyedViewportAnchor(build.container, build.modeAnchor);
        this.#committedRange = build.range;
        this.#activeBuild = null;
        this.#hasCommitted = true;
        for (const retiredContainer of this.#retiredContainers) {
            if (retiredContainer !== build.container) retiredContainer.replaceChildren();
        }
        this.#retiredContainers.clear();
        const emptyState = this.#options.resolveEmptyState?.() ?? null;
        emptyState?.classList.toggle('u-hidden', build.ids.length > 0);
        build.container.classList.toggle('u-hidden', build.ids.length === 0);
        const context: BoundedCollectionCommitContext = { container: build.container, rangeStart: build.range.start, rangeEnd: build.range.end, totalCount: build.ids.length, mountedElements: build.plannedNodes.slice(), enteringElements: build.enteringElements.slice() };
        try {
            this.#options.onCommit?.(context);
        } catch (error) {
            this.#report(ensureError(error));
        }
        this.#commitAwaiter.settle(true);
        if (build.revealId !== null) this.#finishReveal(build.revealId, build.generation);
        const queuedEdge = this.#queuedEdge;
        this.#queuedEdge = null;
        this.#viewport.committed();
        if (queuedEdge !== null && this.#viewport.isAtEdge(queuedEdge)) this.#requestEdge(queuedEdge);
    }

    #requestEdge(edge: CollectionEdge): void {
        if (this.#options.renderAllItems === true) return;
        if (this.#activeBuild !== null) {
            if (this.#activeBuild.edge !== edge) this.#queuedEdge = edge;
            return;
        }
        const range = edge === 'forward' ? createForwardRange(this.#committedRange, this.#ids.length) : createBackwardRange(this.#committedRange, this.#ids.length);
        if (range.start === this.#committedRange.start && range.end === this.#committedRange.end) return;
        this.#scheduleBuild(range, new Set(), edge, false, null, null, { ids: this.#ids, lookup: this.#lookup }, false);
    }

    #requestUnderfill(): void {
        if (this.#disposed || this.#options.renderAllItems === true || this.#activeBuild !== null || this.#committedRange.end >= this.#ids.length) return;
        const retainedLimit = COLLECTION_PAGE_SIZE * COLLECTION_RETAINED_PAGE_COUNT;
        if (this.#committedRange.end - this.#committedRange.start >= retainedLimit) {
            if (!this.#layoutInvariantReported) {
                this.#layoutInvariantReported = true;
                this.#report(new Error(`Collection viewport requires more than the retained ${retainedLimit}-item ceiling`));
            }
            return;
        }
        this.#requestEdge('forward');
    }

    #supersede(): void {
        this.#generation += 1;
        if (this.#buildFrame !== null) this.#resources.cancelAnimationFrame(this.#buildFrame);
        this.#buildFrame = null;
        if (this.#activeBuild !== null) this.#removeBuildLoader(this.#activeBuild);
        this.#activeBuild = null;
        this.#queuedEdge = null;
        this.#settleReveal(false);
    }

    #failBuild(build: CollectionBuild<TItem>, error: Error): void {
        this.#removeBuildLoader(build);
        if (this.#activeBuild === build) {
            this.#ids = build.previousIds;
            this.#lookup = build.previousLookup;
            this.#activeBuild = null;
        }
        this.#queuedEdge = null;
        this.#settleReveal(false);
        if (!this.#hasCommitted) this.#commitAwaiter.settle(false);
        this.#report(error);
    }

    #report(error: Error): void {
        if (this.#options.onError) this.#options.onError(error);
        else errorHandler.error('BoundedCollectionRenderer', 'Collection rendering failed', error);
    }

    #removeBuildLoader(build: CollectionBuild<TItem>): void {
        if (build.loader === null) return;
        const anchor = build.edge === 'backward' ? captureViewportAnchor(build.container) : null;
        build.loader.remove();
        build.loader = null;
        if (anchor !== null) restoreViewportAnchor(build.container, anchor);
    }

    #finishReveal(identifier: string, generation: number): void {
        const container = this.#viewport.container;
        if (generation !== this.#revealGeneration || container === null) return;
        for (const child of container.children) {
            if (child instanceof HTMLElement && child.dataset['collectionId'] === identifier) {
                child.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
                this.#settleReveal(true);
                return;
            }
        }
        this.#settleReveal(false);
    }

    #settleReveal(value: boolean): void {
        this.#revealResolver?.(value);
        this.#revealResolver = null;
        this.#revealGeneration = null;
    }

    #isCurrentBuild(build: CollectionBuild<TItem> | null): build is CollectionBuild<TItem> {
        return build !== null && !this.#disposed && this.#activeBuild === build && build.generation === this.#generation && build.container === this.#options.resolveContainer() && build.container === this.#viewport.container && build.container.isConnected;
    }
}

export { BoundedCollectionRenderer };
