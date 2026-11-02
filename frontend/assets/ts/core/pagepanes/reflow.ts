/* SoAI - Finite resize parking and reconstruction through native pane ownership [frontend/assets/ts/core/pagepanes/reflow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError, isAbortError } from '@core/errors/abort.ts';
import { queryNavigationProtection, subscribeNavigationProtection } from '@core/navigationGuards.ts';
import type { NavigationRequest } from '@core/routing/router/types.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { PagePaneAdmissionDependencies } from '@core/pagepanes/workspaceContracts.ts';
import { PagePaneUnavailableError, type PanePlacementSlot } from '@core/pagepanes/placement.ts';
import { releasePagePaneResources } from '@core/pagepanes/retirement.ts';
import { reportPagePaneActionFailure, reportPagePaneRetirementOutcome } from '@core/pagepanes/notifications.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { reconstructPagePane } from '@core/pagepanes/reconstruction.ts';

interface PagePaneReflowDependencies extends Pick<PagePaneAdmissionDependencies, 'workspace' | 'resources' | 'readAuthEpoch' | 'modalPresenter'> {
    readonly capturePlacement: () => readonly PanePlacementSlot[];
}

class PagePaneReflow {
    readonly #dependencies: PagePaneReflowDependencies;
    readonly #intent = new SequenceToken();
    readonly #attempted = new WeakMap<RoutePane, number>();
    #frame: number | null = null;
    #pending = false;
    #running = false;
    #disposed = false;
    #cancelNavigation: (() => void) | null = null;
    #completion = Promise.resolve();

    constructor(dependencies: PagePaneReflowDependencies) {
        this.#dependencies = dependencies;
        const { workspace, resources } = dependencies;
        resources.track(workspace.subscribeLayout(this.changed));
        resources.track(workspace.subscribeFocusIntent(this.#supersede));
        resources.track(subscribeNavigationProtection(this.changed));
        resources.addEventListener(getWindow(), 'core.modal.close', this.changed);
        resources.track(() => {
            this.#disposed = true;
            this.#supersede();
        });
    }

    get completion(): Promise<void> {
        return this.#completion;
    }

    noteRequest(request: NavigationRequest): void {
        if (request.intent !== 'restore') this.#supersede();
    }

    readonly #supersede = (): void => {
        this.#intent.invalidate();
        const cancel = this.#cancelNavigation;
        this.#cancelNavigation = null;
        cancel?.();
        this.changed();
    };

    readonly changed = (): void => {
        if (this.#disposed) return;
        this.#pending = true;
        if (this.#running || this.#frame !== null) return;
        this.#frame = this.#dependencies.resources.requestAnimationFrame(() => {
            this.#frame = null;
            this.#pending = false;
            this.#running = true;
            this.#completion = this.#reconcile()
                .catch((error) => {
                    if (!isAbortError(error)) reportPagePaneActionFailure(ensureError(error), 'restore');
                })
                .finally(() => {
                    this.#running = false;
                    if (this.#pending) this.changed();
                });
        });
    };

    async #reconcile(): Promise<void> {
        const { workspace, readAuthEpoch } = this.#dependencies;
        const authEpoch = readAuthEpoch();
        const intent = this.#intent.value;
        const current = (): boolean => !this.#disposed && readAuthEpoch() === authEpoch && this.#intent.isActive(intent);
        if (workspace.persistence.restoreRecord || !workspace.getFocusedPane()?.outlet.peekPageHost()?.getCurrentMountScope()?.admission.isActive()) return;
        await this.#parkExcess(authEpoch, current);
        if (current()) await this.#restoreAvailable(current);
    }

    #mountedCount(): number {
        const { workspace } = this.#dependencies;
        return workspace.getPanes().filter((pane) => workspace.getPaneSlot(pane).state !== 'parked').length;
    }

    async #parkExcess(authEpoch: number, current: () => boolean): Promise<void> {
        const { workspace, capturePlacement, modalPresenter, readAuthEpoch } = this.#dependencies;
        for (const pane of [...workspace.getPanes()].reverse()) {
            const capacity = workspace.getCapacity();
            if (!current() || capacity === null || this.#mountedCount() <= capacity || modalPresenter.hasOpenModals()) return;
            const snapshot = capturePlacement().find((entry) => entry.id === pane.id);
            if (!snapshot?.parkable || snapshot.focused || snapshot.state !== 'mounted' || pane.getRequestedRoute()) continue;
            const owner = pane.outlet.peekPageHost()?.getCurrentMountScope();
            if (!owner) throw new Error('A parkable pane requires its active mount');
            const protection = queryNavigationProtection(owner);
            const route = pane.currentRoute;
            const navigation = pane.getLatestNavigationCompletion();
            await pane.outlet.waitForCommit();
            if (!current()) return;
            const latest = capturePlacement().find((entry) => entry.id === pane.id);
            const available = workspace.getCapacity();
            if (available === null || this.#mountedCount() <= available || modalPresenter.hasOpenModals()) return;
            if (!latest?.parkable || latest.focused || latest.state !== 'mounted' || pane.currentRoute !== route || pane.outlet.peekPageHost()?.getCurrentMountScope() !== owner || pane.getLatestNavigationCompletion() !== navigation || pane.getRequestedRoute() || !protection.isCurrent()) continue;
            if (!current() || pane.presentation.isFocused()) continue;
            const releases: (() => void)[] = [];
            const release = (): void => {
                const failures: Error[] = [];
                for (const dispose of releases.splice(0)) runCleanupStepCollectingFailure(dispose, failures);
                throwCollectedCleanupFailures(failures);
            };
            let presentationFailure: Error | null = null;
            try {
                releases.push(owner.admission.blockMutations());
                releases.push(workspace.blockPaneInput(pane));
                workspace.retirePanes([pane]);
            } catch (error) {
                if (workspace.getPaneSlot(pane).state === 'closing') presentationFailure = ensureError(error);
                else {
                    const failures = [ensureError(error)];
                    runCleanupStepCollectingFailure(release, failures);
                    throwCollectedCleanupFailures(failures);
                }
            }
            const outcome = await releasePagePaneResources([{ pane, owner, action: 'park' }], { workspace, modalPresenter, authEpoch, readAuthEpoch, releaseSeals: release });
            reportPagePaneRetirementOutcome(outcome);
            if (presentationFailure) reportPagePaneRetirementOutcome({ type: 'degraded', failures: [{ paneId: pane.id, error: presentationFailure }] });
        }
    }

    async #restoreAvailable(current: () => boolean): Promise<void> {
        const { workspace, modalPresenter } = this.#dependencies;
        const candidates = workspace
            .getPanes()
            .filter((pane) => workspace.getPaneSlot(pane).state === 'parked')
            .sort((left, right) => workspace.getPaneSlot(right).parkedOrdinal - workspace.getPaneSlot(left).parkedOrdinal);
        for (const pane of candidates) {
            const capacity = workspace.getCapacity();
            if (!current() || capacity === null || this.#mountedCount() >= capacity || modalPresenter.hasOpenModals()) return;
            if (!workspace.getPanes().includes(pane) || workspace.getPaneSlot(pane).state !== 'parked' || !pane.currentRoute) continue;
            const parkedOrdinal = workspace.getPaneSlot(pane).parkedOrdinal;
            if (this.#attempted.get(pane) === parkedOrdinal) continue;
            this.#attempted.set(pane, parkedOrdinal);
            try {
                await reconstructPagePane({
                    workspace,
                    pane,
                    route: pane.currentRoute,
                    requireCurrent: () => {
                        if (!current()) throw createAbortError('Resize reconstruction was superseded');
                    },
                    captureCancellation: (cancel) => {
                        this.#cancelNavigation = cancel;
                    }
                });
            } catch (error) {
                if (isAbortError(error) || (error instanceof PagePaneUnavailableError && error.reason === 'capacity-unavailable')) {
                    await pane.outlet.whenReleased();
                    this.#attempted.delete(pane);
                } else if (current() && !isAbortError(error)) reportPagePaneActionFailure(ensureError(error), 'restore');
            } finally {
                this.#cancelNavigation = null;
            }
        }
    }
}

export { PagePaneReflow };
