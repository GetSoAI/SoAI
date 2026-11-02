/* SoAI - Stable pane chrome and keyed switcher row rendering [frontend/assets/ts/core/pagepanes/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { syncTextContent } from '@core/dom/patching.ts';
import { i18n } from '@core/i18n/index.ts';
import { primitives, type ButtonConfig } from '@core/uiprimitives/public.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { joinUiHtml, uiAttributes, uiHtml } from '@core/security/uiHtml.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { PAGE_PANE_CLOSE, PAGE_PANE_SELECT, PAGE_PANE_SPLIT } from '@core/pagepanes/actions.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { RouteEntry } from '@core/routeregistry/contracts.ts';
import type { PagePaneService } from '@core/pagepanes/service.ts';
import type { PageRouting } from '@core/routing/router/types.ts';
import { resolvePagePaneCloseRequest } from '@core/pagepanes/closing.ts';
import { PagePaneUnavailableError } from '@core/pagepanes/placement.ts';
import { resolveRouteTitle } from '@core/routing/router/navigation.ts';

interface PagePaneChrome {
    readonly root: HTMLElement;
    readonly title: HTMLElement;
    readonly close: HTMLButtonElement;
}

interface PagePaneSwitcherEntry {
    readonly paneId: string;
    readonly title: string;
    readonly icon: IconName | null;
    readonly status: 'parked' | 'closing' | 'loading' | 'error' | null;
    readonly selected: boolean;
    readonly canClose: boolean;
}

const capturePagePaneEntries = (workspace: PagePaneService, parseRoute: PageRouting['parseRoute'], targets: readonly RouteEntry[] = []): readonly PagePaneSwitcherEntry[] =>
    workspace.getPanes().map((pane) => {
        const state = workspace.getPaneSlot(pane).state;
        const path = pane.currentRoute ?? pane.getRequestedRoute();
        const parsed = path ? parseRoute(path) : null;
        if (path && !parsed) throw new Error('Pane controls require their registered native route');
        let canClose = true;
        try {
            resolvePagePaneCloseRequest(workspace, pane);
        } catch (error) {
            if (!(error instanceof PagePaneUnavailableError)) throw error;
            canClose = false;
        }
        const host = pane.outlet.peekPageHost();
        const outletState = pane.outlet.getState?.();
        const status = host?.getOwnership().release === 'failed' || outletState === 'error' ? 'error' : state === 'parked' ? 'parked' : state === 'closing' ? 'closing' : state === 'opening' || outletState === 'loading' ? 'loading' : null;
        return { paneId: pane.id, title: parsed ? resolveRouteTitle(parsed.route) : i18n.t('pageOutlet.loading'), icon: targets.find((target) => target.path === parsed?.route.path)?.sidebar?.icon ?? null, status, selected: pane.presentation.isFocused(), canClose };
    });

const createChromeButton = (documentRef: Document, config: ButtonConfig): HTMLButtonElement => {
    const builder = primitives.collection.createBuilder({ pageId: 'page-panes' });
    const host = documentRef.createElement('div');
    dom.setHTML(host, toTrustedUiHtml(builder.button(config)), { escape: false });
    const button = host.firstElementChild;
    if (!(button instanceof HTMLButtonElement)) throw new Error('Pane chrome requires its native button primitive');
    return button;
};

const createPagePaneChrome = (documentRef: Document, paneId: string): PagePaneChrome => {
    const root = documentRef.createElement('div');
    root.className = 'page-pane-chrome';
    root.setAttribute('role', 'group');
    const title = documentRef.createElement('span');
    title.className = 'visually-hidden';
    title.id = `page-pane-${paneId}-title`;
    const controls = documentRef.createElement('div');
    controls.className = 'page-pane-chrome__controls';
    const close = createChromeButton(documentRef, { type: 'button', className: 'ui-round-button ui-round-button--inline ui-round-button--modal-close', icon: 'close', aria: { label: i18n.t('common.close') }, dataset: { action: PAGE_PANE_CLOSE, 'page-pane-id': paneId } });
    controls.append(close);
    root.append(title, controls);
    return { root, title, close };
};

const updatePagePaneChrome = (chrome: PagePaneChrome, entry: PagePaneSwitcherEntry): void => {
    syncTextContent(chrome.title, entry.title);
    chrome.root.setAttribute('aria-label', i18n.t('pagePanes.title'));
    const closeLabel = i18n.t('pagePanes.closePane', { page: entry.title });
    chrome.close.setAttribute('aria-label', closeLabel);
    setTooltipText(chrome.close, entry.canClose ? closeLabel : i18n.t('pagePanes.placementUnavailable'));
    setControlDisabledState(chrome.close, !entry.canClose);
};

const resolvePagePaneStatusText = (entry: PagePaneSwitcherEntry): string => {
    if (entry.status === 'parked') return i18n.t('pagePanes.parked');
    if (entry.status === 'closing') return i18n.t('pagePanes.closing');
    if (entry.status === 'loading') return i18n.t('common.loading');
    if (entry.status === 'error') return i18n.t('common.error');
    return entry.selected ? i18n.t('pagePanes.active') : '';
};

const renderPagePaneRows = (entries: readonly PagePaneSwitcherEntry[]): TrustedHtml => {
    const builder = primitives.collection.createBuilder({ pageId: 'page-panes' });
    return joinUiHtml(
        entries.map((entry) => {
            const select = toTrustedUiHtml(builder.button({ type: 'button', className: 'page-pane-switcher__select', icon: entry.icon ?? undefined, label: entry.title, disabled: entry.status === 'closing', aria: { current: entry.selected ? 'page' : undefined }, dataset: { action: PAGE_PANE_SELECT, 'page-pane-id': entry.paneId } }));
            const close = toTrustedUiHtml(builder.button({ type: 'button', className: 'ui-round-button ui-round-button--inline ui-round-button--neutral', icon: 'close', disabled: !entry.canClose, aria: { label: i18n.t('pagePanes.closePane', { page: entry.title }) }, dataset: { action: PAGE_PANE_CLOSE, 'page-pane-id': entry.paneId } }));
            return uiHtml`<div class="page-pane-switcher__row" role="listitem"${uiAttributes({ 'data-page-pane-entry': entry.paneId, 'data-selected': String(entry.selected), 'data-status': entry.status ?? 'ready' })}>${select}<span class="page-pane-switcher__status">${resolvePagePaneStatusText(entry)}</span>${close}</div>`;
        })
    );
};

const renderPagePaneTargets = (targets: readonly RouteEntry[]): TrustedHtml => {
    const builder = primitives.collection.createBuilder({ pageId: 'page-panes' });
    return joinUiHtml(targets.map((target) => toTrustedUiHtml(builder.button({ type: 'button', className: 'ui-button ui-variant-neutral page-pane-switcher__target', icon: target.sidebar?.icon ?? undefined, label: resolveRouteTitle(target), aria: { label: `${i18n.t('pagePanes.split')}: ${resolveRouteTitle(target)}` }, dataset: { action: PAGE_PANE_SPLIT, 'page-pane-route': target.path } }))));
};

export { renderPagePaneTargets, capturePagePaneEntries, createPagePaneChrome, updatePagePaneChrome, renderPagePaneRows };
export type { PagePaneChrome, PagePaneSwitcherEntry };
