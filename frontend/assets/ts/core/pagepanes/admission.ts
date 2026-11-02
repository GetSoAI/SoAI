/* SoAI - Workspace navigation reservations and synchronous native commit admission [frontend/assets/ts/core/pagepanes/admission.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { evaluateDirtyStateGuardBatch, queryNavigationProtection, resolveNavigationDestructionOwner } from '@core/navigationGuards.ts';
import { decidePanePlacement, PagePaneUnavailableError } from '@core/pagepanes/placement.ts';
import type { PagePaneAdmissionDependencies } from '@core/pagepanes/workspaceContracts.ts';
import type { PaneComponentReservation } from '@core/pagepanes/protection.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { createDestructionNavigationContext, shouldSkipNavigation } from '@core/routing/router/actions.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { NavigationContext, NavigationPlacementAdmission } from '@core/routing/router/types.ts';
import type { PageHostCommitOptions } from '@core/pagehost/types.ts';

import { projectReconstructionRoute } from '@core/routeregistry/reconstruction.ts';
import { PagePaneRestoration } from '@core/pagepanes/restoration.ts';
import { releasePagePaneResources, type PagePaneRetirement, type PagePaneRetirementOutcome } from '@core/pagepanes/retirement.ts';
import { findPagePaneCloseNeighbor, preparePagePaneClose, resolvePagePaneCloseRequest } from '@core/pagepanes/closing.ts';
import { reportPagePaneRetirementOutcome, reportPagePaneSplitHint } from '@core/pagepanes/notifications.ts';
import { PagePaneReflow } from '@core/pagepanes/reflow.ts';
import { anticipatePagePaneExit } from '@core/pagepanes/motion.ts';

interface PagePaneAdmissionResult extends NavigationPlacementAdmission {
    readonly pane: RoutePane;
    readonly historyMode: 'request' | 'replace';
    readonly publication: NonNullable<PageHostCommitOptions['mountPublication']>;
    afterCommit(): Promise<PagePaneRetirementOutcome>;
    present(): void;
}

interface PaneNavigationReservation extends PaneComponentReservation {
    readonly pane: RoutePane;
    readonly context: NavigationContext;
    readonly authEpoch: number;
    readonly focusIntent: number | null;
    readonly opened: boolean;
    opening: boolean;
    committed: boolean;
}

const PAGE_PANE_ANTICIPATED_PROTECTION = new Set(['clean', 'protection-unknown']);

class PagePaneAdmission {
    readonly restoration: PagePaneRestoration;
    readonly reflow: PagePaneReflow;
    readonly #dependencies: PagePaneAdmissionDependencies;
    readonly #reservations = new Map<string, PaneNavigationReservation>();
    #exclusive: PaneNavigationReservation | null = null;
    #guardTail = Promise.resolve();
    #splitHintEpoch: number | null = null;

    constructor(dependencies: PagePaneAdmissionDependencies) {
        this.#dependencies = dependencies;
        this.restoration = new PagePaneRestoration(dependencies);
        this.reflow = new PagePaneReflow({ ...dependencies, capturePlacement: () => dependencies.workspace.capturePlacement(this.#reservations, dependencies.parseRoute, dependencies.readAuthEpoch()) });
    }

    async close(pane: RoutePane): Promise<void> {
        const { workspace, readAuthEpoch } = this.#dependencies;
        const authEpoch = readAuthEpoch();
        const cancelExit = this.#anticipateClose(pane);
        try {
            await pane.outlet.waitForCommit();
            if (readAuthEpoch() !== authEpoch || !workspace.getPanes().includes(pane)) throw createAbortError('Pane closing lost its authenticated owner');
            await pane.navigate(resolvePagePaneCloseRequest(workspace, pane));
        } catch (error) {
            cancelExit?.();
            throw error;
        }
        if (cancelExit && workspace.getPanes().includes(pane) && workspace.getPaneSlot(pane).state !== 'closing' && !workspace.getPaneSlot(pane).root.hidden) cancelExit();
    }

    #anticipateClose(pane: RoutePane): (() => void) | null {
        const { workspace } = this.#dependencies;
        const owner = pane.outlet.peekPageHost()?.getCurrentMountScope() ?? null;
        if (owner !== null && !PAGE_PANE_ANTICIPATED_PROTECTION.has(queryNavigationProtection(owner).reason)) return null;
        try {
            resolvePagePaneCloseRequest(workspace, pane);
        } catch (error) {
            if (error instanceof PagePaneUnavailableError) return null;
            throw ensureError(error);
        }
        return anticipatePagePaneExit(workspace.getPaneSlot(pane).root);
    }

    async admit(origin: RoutePane, context: NavigationContext): Promise<PagePaneAdmissionResult> {
        const { workspace, parseRoute, readAuthEpoch, createPane } = this.#dependencies;
        const authEpoch = readAuthEpoch();
        const automaticRestore = context.request.intent === 'restore';
        const closing = context.request.intent === 'close';
        throwIfAborted(context.signal);
        if (this.#exclusive) throw createAbortError('An exclusive workspace transition owns placement');
        const capturedFocusIntent = origin.getNavigationFocusIntent(context.signal);
        const focusIntent = automaticRestore ? null : capturedFocusIntent;
        const snapshots = workspace.capturePlacement(this.#reservations, parseRoute, authEpoch);
        const originExclusive = origin.currentRoute ? parseRoute(origin.currentRoute)?.route.layout.exclusive === true : false;
        const decision = decidePanePlacement(snapshots, { originId: origin.id, component: context.route.component, intent: context.request.intent ?? 'navigate', exclusive: context.route.layout.exclusive, originExclusive, capacity: workspace.getCapacity() });
        if (decision.type === 'unavailable') throw new PagePaneUnavailableError(decision.reason);
        const panes = workspace.getPanes();
        const displaced = decision.type === 'restore' && decision.displaced ? panes.find((candidate) => candidate.id === decision.displaced?.paneId) : null;
        if (decision.type === 'restore' && decision.displaced && !displaced) throw new Error('Workspace restoration lost its displaced owner');
        const displacedOwner = displaced?.outlet.getPageHost().getCurrentMountScope() ?? null;
        const displacedRoute = displaced?.currentRoute ?? null;
        const displacedNavigation = displaced === origin ? null : displaced?.getLatestNavigationCompletion();
        const displacedReservation = displaced ? this.#reservations.get(displaced.id) : null;
        const parkingProtection = decision.type === 'restore' && decision.displaced?.action === 'park' ? queryNavigationProtection(displacedOwner) : null;
        const opened = decision.type === 'open';
        const targetId = decision.type === 'open' ? null : decision.paneId;
        const pane = opened ? createPane() : panes.find((candidate) => candidate.id === targetId);
        if (!pane) throw new Error('Workspace placement lost its destination');
        const predecessor = this.#reservations.get(pane.id);
        const reservation: PaneNavigationReservation = { pane, context, authEpoch, focusIntent, component: context.route.component, opened: opened || (predecessor?.opened === true && !predecessor.committed), opening: true, committed: false };
        this.#reservations.set(pane.id, reservation);
        if (decision.type === 'exclusive') this.#exclusive = reservation;
        const releases: Array<{ pane: RoutePane; release(): void }> = [];
        let settled = false;
        const releaseSeals = (owner?: RoutePane): void => {
            for (const seal of [...releases].reverse()) {
                if (owner && seal.pane !== owner) continue;
                releases.splice(releases.indexOf(seal), 1);
                seal.release();
            }
        };
        const settle = (): void => {
            if (settled) return;
            settled = true;
            releaseSeals(reservation.committed ? pane : undefined);
            if (this.#exclusive === reservation) this.#exclusive = null;
            if (this.#reservations.get(pane.id) !== reservation) return;
            const release = async (): Promise<void> => {
                await pane.outlet.whenReleased();
                if (this.#reservations.get(pane.id) !== reservation) return;
                if (reservation.opened && !reservation.committed) {
                    if (workspace.getPanes().includes(pane)) {
                        terminateHandledPromise(workspace.removePane(pane));
                        await workspace.whenPaneReleased(pane);
                    } else {
                        pane.disposeNavigation();
                        if (pane.outlet.destroy) await pane.outlet.destroy();
                        else await pane.outlet.destroyCurrent({ force: true });
                    }
                }
                if (this.#reservations.get(pane.id) === reservation) this.#reservations.delete(pane.id);
            };
            void release().catch((error) => errorHandler.warn('PagePaneAdmission', 'Workspace reservation retains unconfirmed resource release', ensureError(error)));
        };
        const validate = (): void => {
            throwIfAborted(context.signal);
            if (readAuthEpoch() !== authEpoch || this.#reservations.get(pane.id) !== reservation || !workspace.getPanes().includes(pane)) throw createAbortError('Workspace placement was superseded');
            if (decision.type === 'exclusive' && !reservation.committed) {
                if (this.#exclusive !== reservation || workspace.getPanes().length !== panes.length || !panes.every((candidate) => workspace.getPanes().includes(candidate))) throw createAbortError('Exclusive workspace membership changed');
                if (focusIntent !== null && !workspace.isCurrentFocusIntent(focusIntent)) throw createAbortError('A newer focus intent protects the workspace');
            } else if (this.#exclusive && this.#exclusive !== reservation) throw createAbortError('Exclusive workspace admission superseded placement');
            if (opened && !reservation.committed) {
                const capacity = workspace.getCapacity();
                if (capacity === null || workspace.capturePlacement(this.#reservations, parseRoute, authEpoch).filter((slot) => slot.visible).length > capacity) throw createAbortError('Workspace capacity changed during preparation');
            }
            if (decision.type === 'restore' && !reservation.committed) {
                const capacity = workspace.getCapacity();
                if (capacity === null || workspace.getPanes().filter((candidate) => candidate !== displaced && candidate.presentation.isVisible()).length >= capacity) throw new PagePaneUnavailableError('capacity-unavailable');
                if (displaced && (!workspace.getPanes().includes(displaced) || displaced.outlet.getPageHost().getCurrentMountScope() !== displacedOwner || displaced.currentRoute !== displacedRoute || displaced.getLatestNavigationCompletion() !== displacedNavigation || this.#reservations.get(displaced.id) !== displacedReservation)) throw createAbortError('The displaced pane acquired a newer owner');
                if (displaced && focusIntent !== null && !workspace.isCurrentFocusIntent(focusIntent) && workspace.getFocusedPane() === displaced) throw createAbortError('A newer focus selection protects the displaced pane');
                if (parkingProtection && (parkingProtection.lossProtected || parkingProtection.explicitDestruction === 'blocked' || !parkingProtection.isCurrent())) throw createAbortError('Clean parking protection changed during preparation');
            }
            if (automaticRestore && !reservation.committed) {
                const current = workspace.capturePlacement(this.#reservations, parseRoute, authEpoch);
                const target = current.find((slot) => slot.id === pane.id);
                const capacity = workspace.getCapacity();
                if (target?.currentComponent === null && !target.visible && (capacity === null || current.filter((slot) => slot.visible).length >= capacity)) throw new PagePaneUnavailableError('capacity-unavailable');
            }
            if (closing && !reservation.committed) {
                if (!findPagePaneCloseNeighbor(workspace, pane)) throw new PagePaneUnavailableError('no-eligible-slot');
                if (workspace.getFocusedPane() === pane && (focusIntent === null || !workspace.isCurrentFocusIntent(focusIntent))) throw createAbortError('A newer focus selection protects the closing pane');
            }
        };
        try {
            origin.transferNavigationTo(pane, context.signal);
            if (opened) await workspace.insertPaneAfter(pane, origin);
            validate();
            await raceWithAbortSignal(pane.outlet.waitForCommit(), context.signal);
            validate();
            if (decision.type === 'target' && decision.capacityHint && this.#splitHintEpoch !== authEpoch) {
                this.#splitHintEpoch = authEpoch;
                reportPagePaneSplitHint();
            }
            const affected = decision.type === 'exclusive' ? panes : displaced ? [displaced] : [pane];
            const retainedRoute = context.request.intent === 'select' && pane.outlet.getPageHost().getCurrent()?.name === context.route.component ? (pane.currentRoute ?? context.request.path) : context.request.path;
            const retained = !closing && affected.length === 1 && (automaticRestore || !context.request.force) && pane.outlet.getPageHost().getCurrentMountScope()?.admission.isActive() === true && shouldSkipNavigation(pane.currentRoute, retainedRoute, pane.outlet);
            if (automaticRestore && ((!retained && pane.outlet.getPageHost().getOwnership().components.length) || projectReconstructionRoute(context.request.path, context.route) !== context.request.path)) throw new PagePaneUnavailableError('restore-conflict');
            const guardContexts = retained || automaticRestore || parkingProtection ? [] : affected.map((candidate) => createDestructionNavigationContext(context, candidate.currentRoute, resolveNavigationDestructionOwner(candidate.outlet.getPageHost().getCurrentMountScope(), authEpoch), parseRoute));
            const validateModalAdmission = (): void => {
                if (
                    (closing || decision.type === 'restore') &&
                    this.#dependencies.modalPresenter.hasOpenModals(
                        decision.type === 'restore' && decision.displaced?.action === 'park'
                            ? []
                            : affected.flatMap((candidate) => {
                                  const owner = candidate.outlet.getPageHost().getCurrentMountScope();
                                  return owner ? [owner] : [];
                              })
                    )
                )
                    throw createAbortError('An unrelated modal protects workspace restoration');
            };
            const present = (): void => {
                if (reservation.committed) {
                    if (context.signal.aborted || readAuthEpoch() !== authEpoch || this.#reservations.get(pane.id) !== reservation || !workspace.getPanes().includes(pane)) return;
                } else validate();
                workspace.reveal(pane);
                if (focusIntent !== null) workspace.focusIfCurrent(pane, focusIntent);
            };
            return {
                pane,
                historyMode: reservation.opened || decision.type === 'restore' ? 'replace' : 'request',
                type: closing ? 'close' : retained ? 'retained' : 'render',
                prepareClose: closing ? () => preparePagePaneClose(workspace.getPaneSlot(pane).root, context.signal) : undefined,
                close: closing
                    ? async (publish) => {
                          validateModalAdmission();
                          validate();
                          const successor = workspace.getFocusedPane() === pane ? findPagePaneCloseNeighbor(workspace, pane) : null;
                          const retirements: PagePaneRetirement[] = [{ pane, owner: pane.outlet.getPageHost().getCurrentMountScope(), action: 'remove' }];
                          reservation.committed = true;
                          reservation.opening = false;
                          workspace.retirePanes([pane], successor);
                          publish();
                          const outcome = await releasePagePaneResources(retirements, { workspace, modalPresenter: this.#dependencies.modalPresenter, authEpoch, readAuthEpoch, releaseSeals });
                          reportPagePaneRetirementOutcome(outcome);
                      }
                    : undefined,
                guardContexts,
                guardPhase: decision.type === 'exclusive' || decision.type === 'restore' ? 'before-commit' : 'before-prepare',
                evaluateGuards: () => {
                    const predecessorTurn = this.#guardTail;
                    const turn = createDeferred<void>();
                    this.#guardTail = turn.promise;
                    const evaluate = async () => {
                        await predecessorTurn;
                        try {
                            validate();
                            return await raceWithAbortSignal(evaluateDirtyStateGuardBatch(guardContexts), context.signal);
                        } finally {
                            turn.resolve();
                        }
                    };
                    return raceWithAbortSignal(evaluate(), context.signal);
                },
                finalAdmission: () => {
                    validate();
                    if (retained) return;
                    validateModalAdmission();
                    try {
                        for (const candidate of affected) {
                            const owner = resolveNavigationDestructionOwner(candidate.outlet.getPageHost().getCurrentMountScope(), authEpoch);
                            if (owner) releases.push({ pane: candidate, release: owner.admission.blockMutations() });
                            releases.push({ pane: candidate, release: workspace.blockPaneInput(candidate) });
                        }
                        validate();
                    } catch (error) {
                        releaseSeals();
                        throw error;
                    }
                },
                publication: {
                    commit: () => {
                        validate();
                        reservation.committed = true;
                        reservation.opening = false;
                    },
                    rollback: () => {
                        reservation.committed = false;
                        reservation.opening = true;
                        releaseSeals();
                    }
                },
                afterCommit: async () => {
                    const retiring = decision.type === 'exclusive' ? panes.filter((candidate) => candidate !== pane) : displaced ? [displaced] : [];
                    if (!retiring.length) return { type: 'released' };
                    const retirements: PagePaneRetirement[] = retiring.map((candidate) => ({ pane: candidate, owner: candidate.outlet.getPageHost().getCurrentMountScope(), action: decision.type === 'restore' && decision.displaced?.action === 'park' ? 'park' : 'remove' }));
                    workspace.retirePanes(retiring);
                    releaseSeals(pane);
                    present();
                    return releasePagePaneResources(retirements, { workspace, modalPresenter: this.#dependencies.modalPresenter, authEpoch, readAuthEpoch, releaseSeals });
                },
                present: () => {
                    releaseSeals(pane);
                    present();
                },
                complete: retained && !automaticRestore ? present : undefined,
                settle
            };
        } catch (error) {
            settle();
            throw error;
        }
    }
}

export { PagePaneAdmission };
export type { PagePaneAdmissionDependencies, PagePaneAdmissionResult };
