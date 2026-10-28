/* SoAI - Bounded contiguous collection renderer [frontend/assets/ts/core/data/boundedcollectionrenderer/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { captureReorderMotion } from '@core/animations/reorderMotion.ts';
import { COLLECTION_BUILD_FRAME_BUDGET_MS, DEFAULT_COLLECTION_RANGE_POLICY, createTargetRange, isRetainedRangeFull, validateCollectionSequence, type CollectionRange, type CollectionRangePolicy } from '@core/data/boundedcollectionrenderer/range.ts';
import { planCollectionBuild, planEdgeRange, planGeometryRange, planUpdateRange, resetCollectionBuildPlan, resolveCollectionRangePolicy, type CollectionRangePlan } from '@core/data/boundedcollectionrenderer/buildPlanning.ts';
import { CollectionCommitAwaiter } from '@core/data/boundedcollectionrenderer/commitAwaiter.ts';
import { captureViewportAnchor, commitPlannedNodes, createEdgeLoader, createPlannedNode, indexExistingCollectionNodes, removeBuildLoader, restoreKeyedViewportAnchor, restoreViewportAnchor, startCollectionExit } from '@core/data/boundedcollectionrenderer/transaction.ts';
import type { BoundedCollectionCommitContext, BoundedCollectionRendererOptions, BoundedCollectionUpdate, CollectionBuild, CollectionEdge, CollectionFocusOwner, CollectionRevealOptions, CollectionSequenceState, CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/types.ts';
import { CollectionRevealTracker } from '@core/data/boundedcollectionrenderer/revealTracker.ts';
import { CollectionViewportCoordinator } from '@core/data/boundedcollectionrenderer/viewportCoordinator.ts';
import { CollectionGridScrollExtent } from '@core/data/boundedcollectionrenderer/gridScrollExtent.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { requirePerformanceNow } from '@core/environment/public.ts';
import { scheduleRequiredRender } from '@core/runtime/animationFrames.ts';
import { canSynchronizeCollectionLookup } from '@core/data/boundedcollectionrenderer/updatePolicy.ts';

class BoundedCollectionRenderer<TItem> {
    readonly #options: BoundedCollectionRendererOptions<TItem>;
    readonly #performanceNow = requirePerformanceNow();
    readonly #viewport = new CollectionViewportCoordinator({ onEdge: (edge) => this.#requestEdge(edge), onUnderfill: () => this.#requestUnderfill(), onContainerReady: () => this.#handleContainerReady(), onScroll: () => this.#handleGridScroll() });
    readonly #gridScrollExtent: CollectionGridScrollExtent | null;
    readonly #retiredContainers = new Set<HTMLElement>();
    #generation = 0;
    #ids: readonly string[] = [];
    #lookup: ReadonlyMap<string, TItem> = new Map();
    #committedRange: CollectionRange = { start: 0, end: 0 };
    #committedPolicy: CollectionRangePolicy = DEFAULT_COLLECTION_RANGE_POLICY;
    #activeBuild: CollectionBuild<TItem> | null = null;
    #queuedEdge: CollectionEdge | null = null;
    #cancelBuild: (() => void) | null = null;
    #disposed = false;
    #hasCommitted = false;
    readonly #commitAwaiter = new CollectionCommitAwaiter();
    readonly #reveals = new CollectionRevealTracker();
    #layoutInvariantReported = false;
    #preparedViewModeAnchor: CollectionViewportAnchor | null = null;
    #viewModeAnchorPrepared = false;

    constructor(options: BoundedCollectionRendererOptions<TItem>) {
        this.#options = options;
        this.#gridScrollExtent = options.preserveGridScrollExtent === true ? new CollectionGridScrollExtent(options.alignRows === true) : null;
    }

    update(input: BoundedCollectionUpdate<TItem>): void {
        if (this.#disposed) return;
        const identifiers = validateCollectionSequence(input.ids, input.lookup);
        if (canSynchronizeCollectionLookup(input, identifiers, this.#ids, this.#activeBuild, this.#hasCommitted, this.#reveals.isPending(), this.#viewModeAnchorPrepared, this.#viewport.container, this.#options.resolveContainer())) {
            this.#lookup = input.lookup;
            if (this.#activeBuild !== null) this.#activeBuild.lookup = input.lookup;
            return;
        }
        const pendingLayoutAnimation = this.#activeBuild?.animateLayout === true;
        const dirtyIds = new Set([...(this.#activeBuild?.dirtyIds ?? []), ...(input.dirtyIds ?? [])]);
        const previousIds = this.#activeBuild?.previousIds ?? this.#ids;
        const previousLookup = this.#activeBuild?.previousLookup ?? this.#lookup;
        const previousRange = this.#committedRange;
        const requestedViewportAnchor = input.restoreViewportAnchor ?? null;
        const restorePreparedViewModeAnchor = this.#viewModeAnchorPrepared || requestedViewportAnchor !== null;
        const viewportAnchor = requestedViewportAnchor ?? (this.#viewModeAnchorPrepared ? this.#preparedViewModeAnchor : this.#resolveVisibleAnchor());
        this.#preparedViewModeAnchor = null;
        this.#viewModeAnchorPrepared = false;
        const anchorId = viewportAnchor?.identifier ?? null;
        const isAppendOnly = previousIds.length > 0 && identifiers.length > previousIds.length && previousIds.every((identifier, index) => identifiers[index] === identifier);
        const extendVisibleEnd = isAppendOnly && previousRange.end === previousIds.length && this.#viewport.isAtEnd();
        this.#supersede();
        this.#ids = identifiers;
        this.#lookup = input.lookup;
        const anchorIndex = anchorId === null ? -1 : identifiers.indexOf(anchorId);
        const resetScroll = input.resetScroll === true || !this.#hasCommitted;
        const planRange = planUpdateRange({ total: identifiers.length, previousRange, anchorIndex, restoreAnchor: requestedViewportAnchor, resetScroll, extendVisibleEnd });
        const animateLayout = (input.animateLayout === true || pendingLayoutAnimation) && this.#hasCommitted && !restorePreparedViewModeAnchor;
        this.#layoutInvariantReported = false;
        if (!this.#scheduleBuild(planRange, dirtyIds, null, resetScroll, null, viewportAnchor, { ids: previousIds, lookup: previousLookup }, restorePreparedViewModeAnchor, animateLayout)) {
            if (!this.#hasCommitted) this.#commitAwaiter.settle(false);
            this.#report(new Error('Collection rendering surface is unavailable'));
        }
    }

    async reveal(identifier: string, options: CollectionRevealOptions = {}): Promise<boolean> {
        const signal = options.signal ?? null;
        if (this.#disposed || signal?.aborted === true) return false;
        const targetIndex = this.#ids.indexOf(identifier);
        if (targetIndex < 0) return false;
        const dirtyIds = this.#activeBuild?.dirtyIds ?? new Set<string>();
        this.#supersede();
        const total = this.#ids.length;
        const result = this.#reveals.begin(this.#generation, signal, () => this.#supersede());
        if (!this.#scheduleBuild((policy) => createTargetRange(targetIndex, total, policy), dirtyIds, null, false, identifier, null, { ids: this.#ids, lookup: this.#lookup }, false, false, options.focusOwner ?? 'renderer')) this.#reveals.settle(false);
        return await result;
    }

    prepareForViewModeChange(): void {
        if (this.#disposed) return;
        this.#preparedViewModeAnchor = this.#resolveVisibleAnchor();
        this.#viewModeAnchorPrepared = true;
    }

    captureViewportAnchor(): CollectionViewportAnchor | null {
        return this.#disposed ? null : this.#resolveVisibleAnchor();
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
        this.#gridScrollExtent?.dispose();
        this.#ids = [];
        this.#lookup = new Map();
        this.#retiredContainers.clear();
        this.#preparedViewModeAnchor = null;
        this.#viewModeAnchorPrepared = false;
        this.#commitAwaiter.settle(false);
    }

    #resolveVisibleAnchor(): CollectionViewportAnchor | null {
        if (this.#gridScrollExtent !== null && this.#viewport.container !== null) return this.#gridScrollExtent.capture(this.#viewport.container, this.#ids, this.#committedPolicy);
        const anchor = this.#viewport.resolveFirstVisibleAnchor();
        return anchor === null || !anchor.atStart || this.#committedRange.start === 0 ? anchor : { ...anchor, atStart: false };
    }

    #scheduleBuild(planRange: CollectionRangePlan, dirtyIds: ReadonlySet<string>, edge: CollectionEdge | null, resetScroll: boolean, revealId: string | null, viewportAnchor: CollectionViewportAnchor | null, previousState: CollectionSequenceState<TItem>, restorePreparedViewModeAnchor: boolean, animateLayout: boolean, focusOwner: CollectionFocusOwner = 'renderer'): boolean {
        const container = this.#options.resolveContainer();
        if (container === null) return false;
        const retiredContainer = this.#viewport.attach(container);
        if (retiredContainer !== null) this.#retiredContainers.add(retiredContainer);
        const gridScrollExtent = this.#gridScrollExtent;
        const resolvedPlan = gridScrollExtent === null ? planRange : (policy: CollectionRangePolicy) => gridScrollExtent.range(container, this.#ids.length, policy, resetScroll || revealId !== null || restorePreparedViewModeAnchor ? planRange(policy) : null);
        const build: CollectionBuild<TItem> = { generation: this.#generation, container, ids: this.#ids, lookup: this.#lookup, planRange: resolvedPlan, policy: null, range: null, dirtyIds, existingNodes: indexExistingCollectionNodes(container), plannedNodes: [], itemPatches: [], enteringElements: [], cursor: 0, loader: null, edge, resetScroll, animateLayout: animateLayout && retiredContainer === null, exitStarted: false, revealId, focusOwner, modeAnchor: restorePreparedViewModeAnchor || retiredContainer !== null ? viewportAnchor : null, previousIds: previousState.ids, previousLookup: previousState.lookup, gridScrollExtent };
        this.#activeBuild = build;
        this.#queueBuildFrame();
        return true;
    }

    #queueBuildFrame(): void {
        if (this.#cancelBuild !== null) return;
        this.#cancelBuild = scheduleRequiredRender(() => {
            this.#cancelBuild = null;
            this.#runBuildSlice();
        });
    }

    #handleContainerReady(): void {
        if (this.#activeBuild !== null) this.#queueBuildFrame();
        const container = this.#viewport.container;
        const policy = this.#options.alignRows === true && container !== null ? resolveCollectionRangePolicy(true, container) : null;
        if (policy === null) return;
        const build = this.#activeBuild;
        if (build !== null) {
            if (build.policy === null || build.policy.rowSize === policy.rowSize) return;
            removeBuildLoader(build);
            resetCollectionBuildPlan(build);
            return;
        }
        if (!this.#hasCommitted || this.#committedPolicy.rowSize === policy.rowSize) return this.#handleGridScroll();
        const anchor = this.#resolveVisibleAnchor();
        const planRange = planGeometryRange(anchor, anchor === null ? -1 : this.#ids.indexOf(anchor.identifier), this.#committedRange, this.#ids.length);
        this.#scheduleBuild(planRange, new Set(), null, false, null, anchor, { ids: this.#ids, lookup: this.#lookup }, true, false);
    }

    #handleGridScroll(): void {
        const container = this.#viewport.container;
        if (this.#gridScrollExtent === null || container === null || !this.#hasCommitted || this.#activeBuild !== null) return;
        try {
            const range = this.#gridScrollExtent.range(container, this.#ids.length, this.#committedPolicy, null);
            if (range.start === this.#committedRange.start && range.end === this.#committedRange.end) return;
            this.#scheduleBuild(() => range, new Set(), null, false, null, null, { ids: this.#ids, lookup: this.#lookup }, false, false);
        } catch (error) {
            this.#report(ensureError(error));
        }
    }

    #runBuildSlice(): void {
        const build = this.#activeBuild;
        if (!this.#isCurrentBuild(build)) return;
        try {
            const range = planCollectionBuild(build, this.#options.alignRows === true);
            if (range === null) return;
            if (build.edge !== null && build.loader === null) {
                const anchor = build.edge === 'backward' ? captureViewportAnchor(build.container) : null;
                build.loader = createEdgeLoader(build.container, build.edge, this.#options.loadingLabel());
                if (build.edge === 'backward') build.container.prepend(build.loader);
                else build.container.append(build.loader);
                if (anchor !== null) restoreViewportAnchor(build.container, anchor);
            }
            if (build.cursor >= range.end) {
                this.#commit(build);
                return;
            }
            const startedAt = this.#performanceNow();
            do {
                const requiredTagName = build.container instanceof HTMLTableSectionElement ? 'TR' : null;
                build.plannedNodes.push(createPlannedNode(build, build.cursor, this.#options.renderItem, this.#options.resolveItemIdentifier, requiredTagName, this.#options.patchMountedItems === true));
                build.cursor += 1;
                if (!this.#isCurrentBuild(build)) return;
            } while (build.cursor < range.end && this.#performanceNow() - startedAt < COLLECTION_BUILD_FRAME_BUDGET_MS);
            if (build.cursor < range.end) {
                this.#queueBuildFrame();
                return;
            }
            this.#commit(build);
        } catch (error) {
            this.#failBuild(build, ensureError(error));
        }
    }

    #commit(build: CollectionBuild<TItem>): void {
        const range = build.range;
        const policy = build.policy;
        if (!this.#isCurrentBuild(build) || range === null || policy === null) return;
        if (startCollectionExit(build, { resume: () => this.#commit(build), fail: (error) => this.#failBuild(build, error) })) return;
        const motion = build.animateLayout ? captureReorderMotion(build.container, (element) => element.dataset['collectionId'] ?? this.#options.resolveItemIdentifier(element), build.previousIds) : null;
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
        if (build.modeAnchor !== null) {
            if (this.#gridScrollExtent !== null) this.#gridScrollExtent.restore(build.container, build.modeAnchor, build.ids, policy);
            else restoreKeyedViewportAnchor(build.container, build.modeAnchor);
        }
        this.#committedRange = range;
        this.#committedPolicy = policy;
        this.#activeBuild = null;
        this.#hasCommitted = true;
        for (const retiredContainer of this.#retiredContainers) {
            if (retiredContainer !== build.container) retiredContainer.replaceChildren();
        }
        this.#retiredContainers.clear();
        const emptyState = this.#options.resolveEmptyState?.() ?? null;
        emptyState?.classList.toggle('u-hidden', build.ids.length > 0);
        build.container.classList.toggle('u-hidden', build.ids.length === 0 && this.#gridScrollExtent === null);
        const context: BoundedCollectionCommitContext = { container: build.container, rangeStart: range.start, rangeEnd: range.end, totalCount: build.ids.length, mountedElements: build.plannedNodes.slice(), enteringElements: motion === null ? build.enteringElements.slice() : [] };
        try {
            this.#options.onCommit?.(context);
        } catch (error) {
            this.#report(ensureError(error));
        }
        motion?.play();
        this.#commitAwaiter.settle(true);
        if (build.revealId !== null) this.#reveals.finish(build.revealId, build.generation, this.#viewport.container, this.#options.resolveItemIdentifier, this.#gridScrollExtent === null ? 'smooth' : 'instant');
        const queuedEdge = this.#queuedEdge;
        this.#queuedEdge = null;
        this.#viewport.committed();
        if (build.revealId === null && build.modeAnchor === null) this.#handleGridScroll();
        if (queuedEdge !== null && this.#viewport.isAtEdge(queuedEdge)) this.#requestEdge(queuedEdge);
    }

    #requestEdge(edge: CollectionEdge): void {
        if (this.#gridScrollExtent !== null) return;
        if (this.#activeBuild !== null) {
            if (this.#activeBuild.edge !== edge) this.#queuedEdge = edge;
            return;
        }
        const committedRange = this.#committedRange;
        const planRange = planEdgeRange(edge, committedRange, this.#ids.length);
        const preview = planRange(this.#committedPolicy);
        if (preview.start === committedRange.start && preview.end === committedRange.end) return;
        this.#scheduleBuild(planRange, new Set(), edge, false, null, null, { ids: this.#ids, lookup: this.#lookup }, false, false);
    }

    #requestUnderfill(): void {
        if (this.#gridScrollExtent !== null || this.#disposed || this.#activeBuild !== null || (this.#committedRange.start === 0 && this.#committedRange.end >= this.#ids.length)) return;
        const retainedLimit = this.#committedPolicy.pageSize * this.#committedPolicy.retainedPageCount;
        if (isRetainedRangeFull(this.#committedRange, this.#committedPolicy)) {
            if (!this.#layoutInvariantReported) {
                this.#layoutInvariantReported = true;
                this.#report(new Error(`Collection viewport requires more than the retained ${retainedLimit}-item ceiling`));
            }
            return;
        }
        this.#requestEdge(this.#committedRange.end < this.#ids.length ? 'forward' : 'backward');
    }

    #supersede(): void {
        this.#generation += 1;
        if (this.#cancelBuild !== null) this.#cancelBuild();
        this.#cancelBuild = null;
        if (this.#activeBuild !== null) removeBuildLoader(this.#activeBuild);
        this.#activeBuild = null;
        this.#queuedEdge = null;
        this.#reveals.settle(false);
    }

    #failBuild(build: CollectionBuild<TItem>, error: Error): void {
        removeBuildLoader(build);
        if (this.#activeBuild === build) {
            this.#ids = build.previousIds;
            this.#lookup = build.previousLookup;
            this.#activeBuild = null;
        }
        this.#queuedEdge = null;
        this.#reveals.settle(false);
        if (!this.#hasCommitted) this.#commitAwaiter.settle(error);
        this.#report(error);
    }

    #report(error: Error): void {
        if (this.#options.onError) this.#options.onError(error);
        else if (claimErrorReporting(error)) errorHandler.error('BoundedCollectionRenderer', 'Collection rendering failed', error);
    }

    #isCurrentBuild(build: CollectionBuild<TItem> | null): build is CollectionBuild<TItem> {
        return build !== null && !this.#disposed && this.#activeBuild === build && build.generation === this.#generation && build.container === this.#options.resolveContainer() && build.container === this.#viewport.container && build.container.isConnected;
    }
}

export { BoundedCollectionRenderer };
