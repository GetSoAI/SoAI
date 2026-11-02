/* SoAI - Authorized primary and finite sibling layout reconstruction [frontend/assets/ts/core/pagepanes/restoration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError, isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { PagePaneWorkspace } from '@core/pagepanes/workspaceContracts.ts';
import type { PagePaneLayoutRecord } from '@core/pagepanes/persistence.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { NavigationRequest, PageRouting } from '@core/routing/router/types.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import { PagePaneUnavailableError } from '@core/pagepanes/placement.ts';
import { reportPagePaneActionFailure } from '@core/pagepanes/notifications.ts';

import { reconstructPagePane, releasePagePaneCandidate } from '@core/pagepanes/reconstruction.ts';
import { reservePagePanes } from '@core/pagepanes/motion.ts';
import { runAsyncCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';

interface PagePaneRestorationDependencies {
    readonly workspace: PagePaneWorkspace;
    readonly createPane: (id?: string) => RoutePane;
    readonly parseRoute: PageRouting['parseRoute'];
    readonly readAuthEpoch: () => number;
}

interface PagePaneRestoreBatch {
    readonly authEpoch: number;
    readonly focusIntent: number;
    readonly primaryRequest: NavigationRequest;
    releaseFocus(): void;
    releaseLayout(): void;
    cancelNavigation(): void;
}

class PagePaneRestoration {
    readonly #dependencies: PagePaneRestorationDependencies;
    #active: PagePaneRestoreBatch | null = null;
    #completion = Promise.resolve();

    constructor(dependencies: PagePaneRestorationDependencies) {
        this.#dependencies = dependencies;
    }

    get completion(): Promise<void> {
        return this.#completion;
    }

    noteRequest(request: NavigationRequest): void {
        const batch = this.#active;
        if (!batch || request === batch.primaryRequest || request.intent === 'restore') return;
        this.#finish(batch, 'superseded');
    }

    #isCurrent(batch: PagePaneRestoreBatch): boolean {
        return this.#active === batch && this.#dependencies.readAuthEpoch() === batch.authEpoch;
    }

    #requireCurrent(batch: PagePaneRestoreBatch): void {
        if (!this.#isCurrent(batch)) throw createAbortError('Layout restoration was superseded');
    }

    #finish(batch: PagePaneRestoreBatch, outcome: 'completed' | 'superseded' | 'failed'): void {
        if (this.#active !== batch) return;
        this.#active = null;
        batch.releaseFocus();
        batch.releaseLayout();
        if (this.#dependencies.readAuthEpoch() === batch.authEpoch) {
            if (outcome === 'failed') this.#dependencies.workspace.persistence.failRestore();
            else this.#dependencies.workspace.persistence.finishRestore();
        }
        if (outcome !== 'completed') batch.cancelNavigation();
    }

    async restorePrimary(incomingRoute: string | null, fallbackRoute: string): Promise<void> {
        const { workspace, createPane, readAuthEpoch } = this.#dependencies;
        const authEpoch = readAuthEpoch();
        const focusIntent = workspace.claimFocusIntent();
        if (readAuthEpoch() !== authEpoch || !workspace.isCurrentFocusIntent(focusIntent)) throw createAbortError('Layout bootstrap lost its authenticated focus admission');
        const decision = workspace.persistence.beginRestore(incomingRoute);
        if (readAuthEpoch() !== authEpoch || !workspace.isCurrentFocusIntent(focusIntent)) throw createAbortError('Layout restore input was superseded');
        const initial = workspace.getFocusedPane() ?? workspace.getPanes()[0];
        if (!initial) throw new Error('Layout restoration requires its allocated primary');
        const route = decision.type === 'restore' ? decision.primary.route : (decision.route ?? fallbackRoute);
        const request = normalizeNavigationRequest(route, { pushState: decision.type === 'restore' && !incomingRoute, replace: true });
        const batch: PagePaneRestoreBatch = { authEpoch, focusIntent, primaryRequest: request, releaseFocus: () => {}, releaseLayout: () => {}, cancelNavigation: () => {} };
        this.#active = batch;
        batch.releaseFocus = workspace.subscribeFocusIntent(() => this.#finish(batch, 'superseded'));
        let primary = initial;
        try {
            if (decision.type === 'restore' && initial.id !== decision.primary.id) {
                if (initial.currentRoute || initial.outlet.getPageHost().getOwnership().components.length || workspace.getPanes().length !== 1) throw new Error('Stored layout cannot replace an existing workspace');
                primary = createPane(decision.primary.id);
                await workspace.insertPaneAfter(primary, initial);
                this.#requireCurrent(batch);
                workspace.reveal(primary);
                if (!workspace.focusIfCurrent(primary, focusIntent)) throw createAbortError('Layout primary lost its focus admission');
                await workspace.removePane(initial);
                await workspace.whenPaneReleased(initial);
                this.#requireCurrent(batch);
            }
            if (decision.type === 'restore') batch.releaseLayout = this.#reserveLayout(primary, decision.record);
            primary.outlet.setSkeleton(route);
            const navigation = primary.navigate(request, focusIntent);
            batch.cancelNavigation = primary.captureCancellation('layout-restoration-superseded');
            await navigation;
            this.#requireCurrent(batch);
            const mounted = workspace.getFocusedPane();
            if (!mounted?.outlet.getPageHost().getCurrentMountScope()?.admission.isActive()) throw new Error('Layout primary did not mount an authorized page');
            batch.cancelNavigation = () => {};
            if (decision.type === 'restore') {
                this.#completion = this.#restoreSiblings(batch, decision.record);
                await this.#completion;
            } else this.#finish(batch, 'completed');
        } catch (error) {
            this.#finish(batch, 'failed');
            throw ensureError(error);
        }
    }

    #reserveLayout(primary: RoutePane, record: PagePaneLayoutRecord): () => void {
        const { workspace } = this.#dependencies;
        const root = workspace.getPaneSlot(primary).root;
        const container = root.parentElement;
        const capacity = workspace.getCapacity() ?? 1;
        if (container === null) return () => {};
        const visible: string[] = [];
        for (const entry of record.panes) {
            if (entry.id === primary.id || (!record.parkedPaneIds.includes(entry.id) && visible.filter((id) => id !== primary.id).length < capacity - 1)) visible.push(entry.id);
        }
        return reservePagePanes(container, root, Math.min(visible.length, capacity), visible.indexOf(primary.id) + 1);
    }

    async #restoreSiblings(batch: PagePaneRestoreBatch, record: PagePaneLayoutRecord): Promise<void> {
        const { workspace, createPane, parseRoute } = this.#dependencies;
        let previous: RoutePane | null = null;
        let outcome: 'completed' | 'failed' = 'completed';
        try {
            for (const entry of record.panes) {
                this.#requireCurrent(batch);
                const preceding = previous;
                let pane = workspace.getPanes().find((candidate) => candidate.id === entry.id);
                if (pane?.outlet.getPageHost().getCurrent()) {
                    previous = pane;
                    continue;
                }
                const component = parseRoute(entry.route)?.route.component;
                const existing = workspace.getPanes().find((candidate) => candidate !== pane && candidate.currentRoute && parseRoute(candidate.currentRoute)?.route.component === component);
                if (existing) continue;
                if (!pane) {
                    pane = createPane(entry.id);
                    try {
                        await workspace.insertPaneAfter(pane, previous);
                        this.#requireCurrent(batch);
                    } catch (error) {
                        const failures = [ensureError(error)];
                        const ownership = pane.outlet.peekPageHost()?.getOwnership();
                        if (!pane.currentRoute && !pane.getRequestedRoute() && (!ownership || (ownership.components.length === 0 && ownership.release === 'settled'))) {
                            const candidate = pane;
                            await runAsyncCleanupStepCollectingFailure(() => releasePagePaneCandidate(workspace, candidate), failures);
                        }
                        throwCollectedCleanupFailures(failures);
                    }
                    pane.currentRoute = entry.route;
                    const parkedIndex = record.parkedPaneIds.indexOf(entry.id);
                    workspace.parkReleasedPane(pane, parkedIndex < 0 ? null : parkedIndex + 1);
                }
                previous = pane;
                const capacity = workspace.getCapacity();
                if (capacity === null || workspace.getPanes().filter((candidate) => candidate.presentation.isVisible()).length >= capacity) continue;
                try {
                    const outcome = await reconstructPagePane({
                        workspace,
                        pane,
                        route: entry.route,
                        requireCurrent: () => this.#requireCurrent(batch),
                        captureCancellation: (cancel) => {
                            batch.cancelNavigation = cancel ?? (() => {});
                        }
                    });
                    if (outcome === 'removed') previous = preceding;
                } catch (error) {
                    if (!this.#isCurrent(batch)) throw ensureError(error);
                    if (error instanceof PagePaneUnavailableError) {
                        if (error.reason === 'restore-conflict') {
                            reportPagePaneActionFailure(error, 'restore');
                            previous = preceding;
                        }
                    } else if (!isAbortError(error)) reportPagePaneActionFailure(ensureError(error), 'restore');
                } finally {
                    batch.cancelNavigation = () => {};
                }
            }
        } catch (error) {
            if (this.#isCurrent(batch)) outcome = 'failed';
            if (this.#isCurrent(batch) && !isAbortError(error)) errorHandler.warn('PagePaneRestoration', 'Remaining layout candidates could not be reconstructed', ensureError(error));
        } finally {
            this.#finish(batch, outcome);
        }
    }
}

export { PagePaneRestoration };
export type { PagePaneRestorationDependencies };
