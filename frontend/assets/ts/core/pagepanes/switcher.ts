/* SoAI - Mount-owned pane switcher interaction and incremental presentation [frontend/assets/ts/core/pagepanes/switcher.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { subscribeNavigationProtection } from '@core/navigationGuards.ts';
import { dom } from '@core/dom/dom.ts';
import { syncTextContent } from '@core/dom/patching.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { i18n } from '@core/i18n/index.ts';
import { LOCALIZATION_CHANGED_EVENT } from '@core/localization/runtime.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { reconcilePresenceList } from '@core/animations/presence/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import type { PagePaneService } from '@core/pagepanes/service.ts';
import type { RouteEntry } from '@core/routeregistry/contracts.ts';
import type { PageMountScope, PageRouting } from '@core/routing/router/types.ts';
import { resolveRouteTitle } from '@core/routing/router/navigation.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { PAGE_PANE_MODAL_ID } from '@core/pagepanes/modal.ts';
import { resolvePagePaneActionFailureMessage, resolvePagePanePersistenceMessage } from '@core/pagepanes/notifications.ts';
import { capturePagePaneEntries, renderPagePaneRows, renderPagePaneTargets } from '@core/pagepanes/view.ts';
import { isPagePaneAction, PAGE_PANE_RECOVER, PAGE_PANE_SPLIT, PAGE_PANE_SELECT, PAGE_PANE_CLOSE, type PagePaneSelection } from '@core/pagepanes/actions.ts';

interface PagePaneSwitcherDependencies {
    readonly workspace: PagePaneService;
    readonly parseRoute: PageRouting['parseRoute'];
    readonly presenter: ModalPresenterApi;
    readonly owner: PageMountScope;
    readonly targets: readonly RouteEntry[];
    readonly targetFailure: Error | null;
    readonly signal: AbortSignal;
}

const showPagePaneSwitcher = async (dependencies: PagePaneSwitcherDependencies): Promise<PagePaneSelection> => {
    const resources = new ResourceTracker();
    try {
        return await runModalSession<PagePaneSelection>({
            owner: dependencies.owner,
            presenter: dependencies.presenter,
            modalId: PAGE_PANE_MODAL_ID,
            signal: dependencies.signal,
            initialResult: null,
            onAlreadyOpen: 'error',
            initialize: (context) => {
                const { modal, signal } = context;
                const list = dom.resolve(modalUiSelector(PAGE_PANE_MODAL_ID, 'list'), modal);
                const targets = dom.resolve(modalUiSelector(PAGE_PANE_MODAL_ID, 'targets'), modal);
                const title = dom.resolve(modalUiSelector(PAGE_PANE_MODAL_ID, 'title'), modal);
                const label = dom.resolve(modalUiSelector(PAGE_PANE_MODAL_ID, 'label'), modal);
                const recovery = dom.resolve(modalUiSelector(PAGE_PANE_MODAL_ID, 'recover'), modal);
                const persistence = dom.resolve(modalUiSelector(PAGE_PANE_MODAL_ID, 'persistence'), modal);
                const status = dom.resolve(modalUiSelector(PAGE_PANE_MODAL_ID, 'status'), modal);
                if (!(list instanceof HTMLElement && targets instanceof HTMLElement && title instanceof HTMLElement && label instanceof HTMLElement && status instanceof HTMLElement && recovery instanceof HTMLButtonElement && persistence instanceof HTMLElement)) throw new Error('Pane switcher modal controls are unavailable');
                const windowRef = modal.ownerDocument.defaultView;
                if (!windowRef) throw new Error('Pane switcher requires its owning document window');
                let targetsLanguage: string | null = null;
                const refresh = (): void => {
                    if (signal.aborted || !dependencies.owner.admission.isCurrent()) return;
                    reconcilePresenceList({ list, rowsHtml: renderPagePaneRows(capturePagePaneEntries(dependencies.workspace, dependencies.parseRoute, dependencies.targets)), emptyStateHtml: uiHtml`<p>${i18n.t('pagePanes.placementUnavailable')}</p>`, resolveRowKey: (row) => row.dataset['pagePaneEntry'] ?? null });
                    syncTextContent(title, i18n.t('pagePanes.title'));
                    syncTextContent(label, i18n.t('pagePanes.choosePage'));
                    const open = new Set(
                        dependencies.workspace.getPanes().map((pane) => {
                            const path = pane.currentRoute ?? pane.getRequestedRoute();
                            return path ? dependencies.parseRoute(path)?.route.path : undefined;
                        })
                    );
                    const capacity = dependencies.workspace.getCapacity();
                    const available = capacity !== null && capacity > 1 ? dependencies.targets.filter((target) => !open.has(target.path)) : [];
                    const language = available.map((target) => `${target.path}\u0001${resolveRouteTitle(target)}`).join('\u0000');
                    if (language !== targetsLanguage) {
                        targetsLanguage = language;
                        dom.setHTML(targets, renderPagePaneTargets(available), { escape: false });
                    }
                    targets.hidden = available.length === 0;
                    label.hidden = available.length === 0;
                    status.hidden = dependencies.targetFailure === null;
                    syncTextContent(status, dependencies.targetFailure ? resolvePagePaneActionFailureMessage(dependencies.targetFailure) : '');
                    const message = resolvePagePanePersistenceMessage(dependencies.workspace.persistence.status);
                    persistence.hidden = message === null;
                    syncTextContent(persistence, message ?? '');
                    recovery.classList.toggle('u-hidden', !dependencies.workspace.persistence.canRecover);
                    syncTextContent(recovery, i18n.t('pagePanes.saveCurrentLayout'));
                    recovery.setAttribute('aria-label', i18n.t('pagePanes.saveCurrentLayout'));
                    setTooltipText(recovery, i18n.t('pagePanes.saveCurrentLayout'));
                };
                const renderQueue = new AnimationFrameRenderQueue<void>({
                    label: 'PagePaneSwitcher',
                    merge: () => undefined,
                    render: refresh,
                    isDisposed: () => signal.aborted,
                    requestAnimationFrame: (callback) => resources.requestAnimationFrame(callback),
                    cancelAnimationFrame: (frame) => resources.cancelAnimationFrame(frame)
                });
                resources.track(() => renderQueue.dispose());
                const schedule = (): void => renderQueue.schedule();
                resources.track(dependencies.workspace.subscribeLayout(schedule), (release) => release());
                resources.track(dependencies.workspace.persistence.subscribe(schedule));
                resources.track(subscribeNavigationProtection(schedule), (release) => release());
                resources.addEventListener(windowRef, LOCALIZATION_CHANGED_EVENT, schedule);
                const act = ({ action, actionElement }: { action: string; actionElement: HTMLElement }): void => {
                    if (signal.aborted || !dependencies.owner.admission.isActive()) return;
                    if (action === PAGE_PANE_RECOVER) {
                        if (!dependencies.workspace.persistence.canRecover) return;
                        context.setResult({ type: 'recover' });
                    } else if (action === PAGE_PANE_SPLIT) {
                        const route = actionElement.dataset['pagePaneRoute'];
                        if (!route || !dependencies.targets.some((target) => target.path === route)) throw new Error('Pane split selection is not an admitted route');
                        context.setResult({ type: 'split', route });
                    } else if (action === PAGE_PANE_SELECT || action === PAGE_PANE_CLOSE) {
                        const paneId = actionElement.dataset['pagePaneId'];
                        if (!paneId || !dependencies.workspace.getPanes().some((pane) => pane.id === paneId)) return;
                        context.setResult({ type: action === PAGE_PANE_SELECT ? 'select' : 'close', paneId });
                    } else throw new Error('Pane switcher received a chrome-only action');
                    context.close('pane-action', { restoreFocus: false });
                };
                bindDataActionListener({ root: modal, signal, eventType: 'click', isAction: isPagePaneAction, onAction: act, preventDefault: 'interactive', ignoreFormControls: true });
                refresh();
                return { dispose: () => resources.dispose() };
            }
        });
    } finally {
        await resources.dispose();
    }
};

export { showPagePaneSwitcher };
