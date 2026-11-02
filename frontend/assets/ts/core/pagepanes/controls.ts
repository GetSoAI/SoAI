/* SoAI - Document-owned pane controls with captured mount and user intent [frontend/assets/ts/core/pagepanes/controls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { subscribeNavigationProtection } from '@core/navigationGuards.ts';
import { getWindow } from '@core/environment/public.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { createGlobalPresentationOwner } from '@core/presentationOwner.ts';
import { getHeaderActions } from '@core/headeractions/public.ts';
import type { HeaderActionRegistration } from '@core/headeractions/types.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import { i18n } from '@core/i18n/index.ts';
import { LOCALIZATION_CHANGED_EVENT } from '@core/localization/runtime.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { GlobalPresentationOwner } from '@core/routing/router/types.ts';
import type { AuthService } from '@core/routing/router/routerDependencies.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { RouteEntry } from '@core/routeregistry/contracts.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { PagePaneService } from '@core/pagepanes/service.ts';
import { PagePaneUnavailableError } from '@core/pagepanes/placement.ts';
import { createPagePaneChrome, updatePagePaneChrome, capturePagePaneEntries, type PagePaneChrome } from '@core/pagepanes/view.ts';
import { showPagePaneSwitcher } from '@core/pagepanes/switcher.ts';
import { isPagePaneAction, PAGE_PANE_CLOSE, type PagePaneSelection } from '@core/pagepanes/actions.ts';
import { reportPagePaneActionFailure, resolvePagePanePersistenceMessage } from '@core/pagepanes/notifications.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';

type PagePaneTargetsOutcome = { readonly type: 'ready'; readonly targets: readonly RouteEntry[] } | { readonly type: 'unavailable'; readonly error: Error };

interface PagePaneControlsDependencies {
    readonly workspace: PagePaneService;
    readonly router: Pick<Router, 'navigate' | 'parseRoute'>;
    readonly auth: Pick<AuthService, 'authEpoch' | 'isAuthenticated'>;
    readonly presenter: ModalPresenterApi;
    readonly readTargets: (signal: AbortSignal) => Promise<PagePaneTargetsOutcome>;
}

class PagePaneControls {
    readonly #dependencies: PagePaneControlsDependencies;
    readonly #resources = new ResourceTracker();
    readonly #scope = new LifecycleScope();
    readonly #owner = createGlobalPresentationOwner('page-pane-controls');
    readonly #chrome = new WeakMap<RoutePane, PagePaneChrome>();
    readonly #roots = new WeakSet<HTMLElement>();
    #registration: HeaderActionRegistration<GlobalPresentationOwner> | null = null;
    readonly #renderQueue = new AnimationFrameRenderQueue<void>({
        label: 'PagePaneControls',
        merge: () => undefined,
        isDisposed: () => this.#disposed,
        requestAnimationFrame: (callback) => this.#resources.requestAnimationFrame(callback),
        cancelAnimationFrame: (frame) => this.#resources.cancelAnimationFrame(frame),
        render: () => {
            try {
                this.#render();
            } catch (error) {
                reportPagePaneActionFailure(ensureError(error));
            }
        }
    });
    #initialized = false;
    #disposed = false;
    #opening = false;
    #modalCompletion: Promise<PagePaneSelection> | null = null;
    #disposal: Promise<void> | null = null;

    constructor(dependencies: PagePaneControlsDependencies) {
        this.#dependencies = dependencies;
    }

    initialize(): void {
        if (this.#disposed) throw new Error('Disposed pane controls cannot initialize');
        if (this.#initialized) return;
        this.#initialized = true;
        this.#scope.begin();
        this.#resources.track(() => this.#renderQueue.dispose());
        this.#registration = getHeaderActions().createRegistration(this.#owner);
        this.#resources.track(this.#dependencies.workspace.subscribeLayout(this.#schedule));
        this.#resources.track(this.#dependencies.workspace.persistence.subscribe(this.#schedule));
        this.#resources.track(subscribeNavigationProtection(this.#schedule));
        this.#resources.addEventListener(getWindow(), LOCALIZATION_CHANGED_EVENT, this.#schedule);
        this.#schedule();
    }

    readonly #schedule = (): void => this.#renderQueue.schedule();

    readonly #openAction = (): void => {
        void this.open().catch((error) => reportPagePaneActionFailure(ensureError(error)));
    };

    #render(): void {
        const { workspace, router, auth } = this.#dependencies;
        const panes = workspace.getPanes();
        if (!this.#registration) throw new Error('Pane controls require their header registration');
        if (!panes.length) return;
        const entries = capturePagePaneEntries(workspace, (path) => router.parseRoute(path));
        for (const pane of panes) {
            const slot = workspace.getPaneSlot(pane);
            let chrome = this.#chrome.get(pane);
            if (!chrome) {
                chrome = createPagePaneChrome(slot.root.ownerDocument, pane.id);
                slot.root.prepend(chrome.root);
                slot.root.setAttribute('role', 'region');
                slot.root.setAttribute('aria-labelledby', chrome.title.id);
                this.#chrome.set(pane, chrome);
            }
            const entry = entries.find((candidate) => candidate.paneId === pane.id);
            if (!entry) throw new Error('Pane chrome lost its native presentation entry');
            updatePagePaneChrome(chrome, entry);
            const root = slot.root.parentElement;
            if (root && !this.#roots.has(root)) {
                bindDataActionListener({
                    root,
                    signal: this.#scope.current().signal,
                    eventType: 'click',
                    isAction: isPagePaneAction,
                    beforeEvent: (event) => !(event.target instanceof Element) || event.target.closest('.page-pane-chrome') === null,
                    onAction: async ({ action, actionElement }) => {
                        const current = workspace.getPanes().find((candidate) => candidate.id === actionElement.dataset['pagePaneId']);
                        if (!current || !this.#chrome.get(current)?.root.contains(actionElement)) return;
                        try {
                            if (action === PAGE_PANE_CLOSE) await workspace.navigation.close(current);
                            else throw new Error('Pane chrome received a switcher-only action');
                        } catch (error) {
                            reportPagePaneActionFailure(ensureError(error));
                        }
                    },
                    preventDefault: 'interactive'
                });
                this.#roots.add(root);
            }
        }
        const selected = workspace.getFocusedPane();
        const route = selected?.currentRoute ? router.parseRoute(selected.currentRoute)?.route : null;
        const usable = selected?.outlet.peekPageHost()?.getCurrentMountScope()?.admission.isActive() === true;
        const persistenceMessage = resolvePagePanePersistenceMessage(workspace.persistence.status);
        const management = panes.length > 1 || workspace.persistence.canRecover;
        const className = `header-action--panes ${management ? 'header-action--panes-management ' : ''}${persistenceMessage ? 'ui-variant-warning' : 'ui-variant-neutral'}`;
        getHeaderActions().defineAction(HEADER_ACTION_IDS.panes, this.#owner, { icon: 'panel-left-visible', order: 35, label: i18n.t('pagePanes.title'), ariaLabel: i18n.t('pagePanes.title'), tooltip: persistenceMessage ?? i18n.t('pagePanes.title'), className, onClick: this.#openAction });
        getHeaderActions().setActionState(HEADER_ACTION_IDS.panes, 'page-pane-controls', this.#registration, { visible: auth.isAuthenticated && panes.length > 0 && route?.layout.exclusive !== true, disabled: !usable || this.#opening, badge: panes.length > 1 ? i18n.formatNumber(panes.length) : undefined });
    }

    async open(): Promise<void> {
        if (this.#disposed || this.#opening) return;
        this.#opening = true;
        try {
            this.#schedule();
            const { workspace, router, auth, presenter, readTargets } = this.#dependencies;
            const owner = workspace.getFocusedPane()?.outlet.peekPageHost()?.getCurrentMountScope();
            const authEpoch = auth.authEpoch;
            if (!auth.isAuthenticated || !owner?.admission.isActive()) return;
            if (presenter.hasOpenModals()) throw new PagePaneUnavailableError('no-eligible-slot');
            const focusIntent = workspace.claimFocusIntent();
            const current = (): boolean => !this.#disposed && auth.authEpoch === authEpoch && auth.isAuthenticated && owner.admission.isActive() && workspace.isCurrentFocusIntent(focusIntent);
            if (!current()) return;
            const targets = await readTargets(this.#scope.current().signal);
            if (!current()) return;
            const completion = showPagePaneSwitcher({ workspace, parseRoute: (path) => router.parseRoute(path), presenter, owner, targets: targets.type === 'ready' ? targets.targets : [], targetFailure: targets.type === 'unavailable' ? targets.error : null, signal: this.#scope.current().signal });
            this.#modalCompletion = completion;
            const selection = await completion;
            if (this.#modalCompletion === completion) this.#modalCompletion = null;
            if (!selection || !current()) return;
            if (selection.type === 'recover') {
                const recovery = workspace.persistence.prepareRecovery();
                if (!recovery || !current()) return;
                if (recovery.requiresConfirmation) {
                    const confirmed = await requireDialogsService().showConfirmation({ owner, signal: this.#scope.current().signal, title: i18n.t('pagePanes.saveCurrentLayout'), message: i18n.t('pagePanes.replaceSavedLayoutConfirmation'), confirmText: i18n.t('pagePanes.saveCurrentLayout'), variant: 'warning' });
                    if (!confirmed || !current()) return;
                }
                recovery.commit();
            } else if (selection.type === 'split') await router.navigate(selection.route, { intent: 'split' });
            else {
                const target = workspace.getPanes().find((candidate) => candidate.id === selection.paneId);
                if (!target) return;
                if (selection.type === 'close') await workspace.navigation.close(target);
                else if (target.currentRoute) await router.navigate(target.currentRoute, { intent: 'select', force: target.outlet.getState?.() === 'error' });
            }
        } catch (error) {
            reportPagePaneActionFailure(ensureError(error));
        } finally {
            this.#opening = false;
            this.#modalCompletion = null;
            this.#schedule();
        }
    }

    dispose(): Promise<void> {
        if (this.#disposal) return this.#disposal;
        const completion = createDeferred<void>();
        this.#disposal = completion.promise;
        this.#disposed = true;
        void this.#release().then(completion.resolve, (error) => completion.reject(ensureError(error)));
        return completion.promise;
    }

    async #release(): Promise<void> {
        const failures: Error[] = [];
        runCleanupStepCollectingFailure(() => this.#resources.seal(), failures);
        runCleanupStepCollectingFailure(() => this.#scope.abort('pane-controls-disposed'), failures);
        runCleanupStepCollectingFailure(() => {
            if (this.#registration) getHeaderActions().removeActionContext(HEADER_ACTION_IDS.panes, 'page-pane-controls', this.#registration);
        }, failures);
        const outcomes = await Promise.allSettled([this.#resources.dispose(), this.#modalCompletion]);
        failures.push(...outcomes.flatMap((outcome) => (outcome.status === 'rejected' ? [ensureError(outcome.reason)] : [])));
        throwCollectedCleanupFailures(failures);
    }
}

export { PagePaneControls };
export type { PagePaneControlsDependencies, PagePaneTargetsOutcome };
