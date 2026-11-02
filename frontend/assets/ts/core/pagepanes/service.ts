/* SoAI - Stable workspace slots and pane presentation ownership [frontend/assets/ts/core/pagepanes/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { EventBus } from '@core/EventBus.ts';
import { syncAttributeValue } from '@core/dom/patching.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { PagePaneGeometry } from '@core/pagepanes/geometry.ts';
import { PagePaneFocus } from '@core/pagepanes/focus.ts';
import { createPagePaneSlot, allocatePagePaneSlot, findPagePaneSlot, requirePagePaneSlot, insertPagePaneRoot } from '@core/pagepanes/dom.ts';
import type { PagePaneSlot } from '@core/pagepanes/contracts.ts';
import type { PaneCapacity } from '@core/pagepanes/capacity.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { runAsyncCleanupStepCollectingFailure, runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { blockPageContentInput, isPageContentAvailable, setPageContentAvailable } from '@core/layout/pageContentInteractivity.ts';
import type { PageMountScope, PageRouting } from '@core/routing/router/types.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { PanePlacementSlot } from '@core/pagepanes/placement.ts';
import { capturePanePlacement, type PaneComponentReservation } from '@core/pagepanes/protection.ts';
import { PagePaneAdmission } from '@core/pagepanes/admission.ts';
import type { PagePaneAdmissionDependencies, PagePaneWorkspace } from '@core/pagepanes/workspaceContracts.ts';
import { isBoolean, isNumber } from '@core/typeGuards.ts';
import { PagePanePersistence } from '@core/pagepanes/session.ts';

class PagePaneService implements PagePaneWorkspace {
    readonly #slots = new Map<string, PagePaneSlot>();
    readonly #events = new EventBus();
    readonly #removals = new WeakMap<RoutePane, { actual: Promise<void>; wait: Promise<void> }>();
    readonly #resources = new ResourceTracker();
    readonly persistence = new PagePanePersistence(
        () => this.#slots.values(),
        () => this.#focus.selected?.id ?? null
    );
    readonly #geometry = new PagePaneGeometry(
        this.#resources,
        (capacity) => {
            this.#projectLayout(capacity);
        },
        (error) => errorHandler.warn('PagePaneService', 'Split layout measurement unavailable', error)
    );
    #container: HTMLElement | null = null;
    #placementRevision = 0;
    #admission: PagePaneAdmission | null = null;
    readonly #focus = new PagePaneFocus(
        this.#slots,
        () => this.#container,
        (focusChanged, userIntent) => {
            const samePaneSelection = userIntent && !focusChanged;
            if (!samePaneSelection) {
                this.refreshFocusedProjection();
                this.persistence.changed();
            }
            if (focusChanged || userIntent) this.#events.emit('focus', userIntent);
        },
        (intent) => this.#events.emit('intent', intent)
    );

    attach(container: HTMLElement, primary: RoutePane): HTMLElement {
        if (this.#container) {
            if (this.#container !== container) throw new Error('A workspace cannot change its allocation root');
            const existing = this.#slots.get(primary.id);
            if (!existing || existing.pane !== primary) throw new Error('Workspace primary pane does not match');
            return existing.outlet;
        }
        const originalNodes = Array.from(container.childNodes);
        const slot = createPagePaneSlot(primary, container.ownerDocument, 'mounted');
        const listeners: (() => void)[] = [];
        slot.outlet.append(...originalNodes);
        try {
            primary.outlet.setContainer(slot.outlet);
            container.append(slot.root);
            listeners.push(this.#resources.addEventListener(container, 'pointerdown', this.#focus.handleEvent, { capture: true }));
            listeners.push(this.#resources.addEventListener(container, 'focusin', this.#focus.handleEvent, { capture: true }));
        } catch (error) {
            const failures = [ensureError(error)];
            for (const release of listeners) runCleanupStepCollectingFailure(release, failures);
            container.append(...originalNodes);
            slot.root.remove();
            throw new AggregateError(failures, 'Workspace attachment failed');
        }
        container.classList.add('page-workspace');
        this.#container = container;
        this.#slots.set(primary.id, slot);
        this.#placementRevision += 1;
        this.focus(primary);
        this.#geometry.observe(container);
        return slot.outlet;
    }

    getFocusedPane(): RoutePane | null {
        return this.#focus.selected;
    }

    configureAdmission(dependencies: Omit<PagePaneAdmissionDependencies, 'workspace' | 'resources'>): void {
        if (this.#admission) throw new Error('Workspace navigation admission is already configured');
        this.#admission = new PagePaneAdmission({ ...dependencies, workspace: this, resources: this.#resources });
    }

    get navigation(): PagePaneAdmission {
        if (!this.#admission) throw new Error('Workspace navigation admission is not configured');
        return this.#admission;
    }

    get placementRevision(): number {
        return this.#placementRevision;
    }

    claimFocusIntent(): number {
        return this.#focus.claimIntent();
    }

    isCurrentFocusIntent(intent: number): boolean {
        return this.#focus.isCurrentIntent(intent);
    }

    focusIfCurrent(pane: RoutePane, intent: number): boolean {
        if (!this.#focus.isCurrentIntent(intent) || !this.#focus.canSelect(pane)) return false;
        this.#focus.select(pane, false);
        return true;
    }

    capturePlacement(requested: ReadonlyMap<string, PaneComponentReservation>, parseRoute: PageRouting['parseRoute'], authEpoch: number): readonly PanePlacementSlot[] {
        return capturePanePlacement(this.#slots.values(), this.#focus.selected, requested, parseRoute, authEpoch);
    }

    blockPaneInput(pane: RoutePane): () => void {
        return blockPageContentInput(requirePagePaneSlot(pane, this.#slots).root);
    }

    retirePanes(panes: readonly RoutePane[], successor: RoutePane | null = null): void {
        if (new Set(panes).size !== panes.length) throw new Error('Pane retirement requires unique owners');
        if (successor && (panes.includes(successor) || requirePagePaneSlot(successor, this.#slots).state !== 'mounted')) throw new Error('A retirement successor requires a surviving mounted owner');
        const slots = panes.map((pane) => requirePagePaneSlot(pane, this.#slots));
        for (const slot of slots) {
            slot.state = 'closing';
        }
        this.#placementRevision += 1;
        this.#projectLayout(undefined, successor);
    }

    async insertPaneAfter(pane: RoutePane, after: RoutePane | null): Promise<void> {
        const container = this.#container;
        if (!container) throw new Error('A new pane requires its allocated workspace root');
        const origin = after ? requirePagePaneSlot(after, this.#slots) : null;
        const slot = allocatePagePaneSlot(pane, after, this.#slots, container.ownerDocument);
        this.#placementRevision += 1;
        const wasAvailable = isPageContentAvailable(container);
        const requireAllocation = (): void => {
            if (this.#container !== container || this.#slots.get(pane.id) !== slot || (after && this.#slots.get(after.id) !== origin) || slot.state !== 'opening' || !slot.admitted || (wasAvailable && !isPageContentAvailable(container))) throw createAbortError('Workspace pane allocation was superseded');
        };
        try {
            pane.outlet.setContainer(slot.outlet);
            requireAllocation();
            pane.setPresentation({ visible: true, focused: false });
            requireAllocation();
            insertPagePaneRoot(slot, container, this.#slots);
            this.#projectLayout();
            requireAllocation();
        } catch (error) {
            const failures: Error[] = [];
            await runAsyncCleanupStepCollectingFailure(() => this.removePane(pane), failures);
            if (failures.length) throw new AggregateError([ensureError(error), ...failures], 'Workspace pane allocation cleanup incomplete');
            throw ensureError(error);
        }
        this.#geometry.refresh();
    }

    removePane(pane: RoutePane): Promise<void> {
        const existing = this.#removals.get(pane);
        if (existing) return existing.wait;
        const slot = this.#slots.get(pane.id);
        if (!slot || slot.pane !== pane) return Promise.reject(new Error('Cannot remove a pane outside its workspace'));
        if (this.#focus.selected === pane) return Promise.reject(new Error('A focused pane requires a committed neighbor before removal'));
        const caller = createDeferred<void>();
        const release = async (): Promise<void> => {
            const failures: Error[] = [];
            runCleanupStepCollectingFailure(() => pane.setPresentation({ visible: false, focused: false }), failures);
            runCleanupStepCollectingFailure(() => pane.disposeNavigation(), failures);
            let wait: Promise<void>;
            try {
                wait = pane.outlet.destroy ? pane.outlet.destroy() : pane.outlet.destroyCurrent({ force: true });
            } catch (error) {
                const failure = ensureError(error);
                failures.push(failure);
                wait = Promise.reject(failure);
            }
            void wait.catch((error) => caller.reject(ensureError(error)));
            await runAsyncCleanupStepCollectingFailure(() => pane.outlet.whenReleased(), failures);
            throwCollectedCleanupFailures(failures);
            if (this.#slots.get(pane.id) !== slot) throw new Error('Workspace removal lost its slot ownership');
            this.#slots.delete(pane.id);
            this.#placementRevision += 1;
            slot.root.remove();
            this.#projectLayout();
            this.#geometry.refresh();
        };
        const actual = Promise.resolve().then(release);
        this.#removals.set(pane, { actual, wait: caller.promise });
        if (slot.state !== 'closing') {
            slot.state = 'closing';
            this.#placementRevision += 1;
        }
        this.#projectLayout();
        this.persistence.changed();
        void actual.then(caller.resolve, (error) => caller.reject(ensureError(error)));
        return caller.promise;
    }

    whenPaneReleased(pane: RoutePane): Promise<void> | null {
        return this.#removals.get(pane)?.actual ?? null;
    }

    parkReleasedPane(pane: RoutePane, parkedOrdinal: number | null = null): void {
        const slot = requirePagePaneSlot(pane, this.#slots);
        const ownership = pane.outlet.getPageHost().getOwnership();
        if (this.#focus.selected === pane || !pane.currentRoute || ownership.components.length || ownership.release !== 'settled') throw new Error('Parking requires an unfocused reconstruction route with confirmed resource release');
        if (parkedOrdinal !== null && (!Number.isSafeInteger(parkedOrdinal) || parkedOrdinal < 1)) throw new Error('Stored parking order requires a positive safe ordinal');
        slot.state = 'parked';
        this.#placementRevision = Math.max(this.#placementRevision, parkedOrdinal ?? 0) + 1;
        slot.parkedOrdinal = parkedOrdinal ?? this.#placementRevision;
        this.#projectLayout();
    }

    refreshFocusedProjection(): void {
        const container = this.#container;
        if (!container) return;
        const outlet = isPageContentAvailable(container) && this.#focus.selected?.presentation.isVisible() ? this.#focus.selected.outlet.getContainer() : null;
        const activePage = outlet?.dataset['activePage'];
        syncAttributeValue(container, 'data-active-page', activePage ?? null);
        const state = outlet?.dataset['pageOutletState'];
        syncAttributeValue(container, 'data-page-outlet-state', state ?? null);
        this.#events.emit('layout');
    }

    getPanes(): readonly RoutePane[] {
        return [...this.#slots.values()].map((slot) => slot.pane);
    }

    getPaneSlot(pane: RoutePane): Readonly<PagePaneSlot> {
        return requirePagePaneSlot(pane, this.#slots);
    }

    getCapacity(): PaneCapacity | null {
        return this.#geometry.getCapacity();
    }

    subscribeLayout(listener: () => void): () => void {
        return this.#events.on('layout', listener);
    }

    getMountScopeForElement(element: Element): PageMountScope | null {
        const slot = findPagePaneSlot(element, this.#container, this.#slots);
        return slot?.pane.outlet.getPageHost().getCurrentMountScope() ?? null;
    }

    subscribeFocus(listener: (userIntent: boolean) => void): () => void {
        return this.#events.on('focus', (event) => {
            if (event instanceof CustomEvent && isBoolean(event.detail)) listener(event.detail);
        });
    }

    subscribeFocusIntent(listener: (intent: number) => void): () => void {
        return this.#events.on('intent', (event) => {
            if (event instanceof CustomEvent && isNumber(event.detail)) listener(event.detail);
        });
    }

    focus(pane: RoutePane): void {
        this.#focus.select(pane, true);
    }

    invalidateSession(): void {
        const cancellations = [...this.#slots.values()].map((slot) => slot.pane.captureSessionCancellation('authentication-invalidated'));
        const invalidatePersistence = this.persistence.captureInvalidation();
        this.#placementRevision += 1;
        const failures: Error[] = [];
        runCleanupStepCollectingFailure(() => this.#geometry.reset(), failures);
        for (const cancellation of cancellations) runCleanupStepCollectingFailure(cancellation.seal, failures);
        runCleanupStepCollectingFailure(() => this.#focus.suspend([invalidatePersistence, ...cancellations.map((cancellation) => cancellation.cancel)]), failures);
        runCleanupStepCollectingFailure(() => this.refreshFocusedProjection(), failures);
        if (failures.length) throw new AggregateError(failures, 'Workspace authentication invalidation failed');
    }

    reveal(pane: RoutePane): void {
        const slot = this.#slots.get(pane.id);
        if (!slot || slot.pane !== pane || !this.#container) throw new Error('Cannot reveal a pane outside its workspace');
        const owner = pane.outlet.getPageHost().getCurrentMountScope();
        if (owner && !owner.admission.isCurrent()) throw createAbortError('Pane reveal no longer owns its authenticated mount');
        setPageContentAvailable(this.#container, true);
        slot.admitted = true;
        if (slot.state !== 'mounted') {
            slot.state = 'mounted';
            this.#placementRevision += 1;
        }
        this.#projectLayout();
        this.refreshFocusedProjection();
        this.#geometry.refresh();
    }

    #projectLayout(capacity = this.#geometry.getCapacity(), successor: RoutePane | null = null): void {
        try {
            this.#focus.project(capacity, false, false, undefined, successor);
        } catch (error) {
            errorHandler.warn('PagePaneService', 'Pane layout presentation failed', ensureError(error));
        }
    }

    async detach(): Promise<void> {
        for (const slot of this.#slots.values()) {
            if (slot.state === 'closing' || slot.pane.outlet.getPageHost().getOwnership().components.length) throw new Error('Workspace cannot detach while page resources remain owned');
        }
        const failures: Error[] = [];
        runCleanupStepCollectingFailure(() => this.#geometry.dispose(), failures);
        await runAsyncCleanupStepCollectingFailure(() => this.#resources.cleanup({ requireComplete: true }), failures);
        throwCollectedCleanupFailures(failures);
        for (const slot of this.#slots.values()) slot.root.remove();
        this.#slots.clear();
        this.#placementRevision += 1;
        this.#focus.reset();
        this.#container?.classList.remove('page-workspace');
        if (this.#container) {
            delete this.#container.dataset['activePage'];
            delete this.#container.dataset['pageOutletState'];
        }
        this.#container = null;
    }
}

export { PagePaneService };
