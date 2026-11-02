/* SoAI - Native workspace slot roots and origin resolution [frontend/assets/ts/core/pagepanes/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PagePaneSlot } from '@core/pagepanes/contracts.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import { setPageContentReady } from '@core/layout/pageContentInteractivity.ts';
import { dom } from '@core/dom/dom.ts';

const createPagePaneSlot = (pane: RoutePane, documentRef: Document, state: PagePaneSlot['state']): PagePaneSlot => {
    const root = documentRef.createElement('div');
    root.className = 'page-pane';
    root.hidden = true;
    root.dataset['pagePaneId'] = pane.id;
    root.dataset['paneFocused'] = 'false';
    setPageContentReady(root, state !== 'opening');
    const outlet = documentRef.createElement('div');
    outlet.className = 'page-pane-outlet';
    root.append(outlet);
    return { pane, root, outlet, focusOrdinal: 0, parkedOrdinal: 0, state, admitted: true };
};

const findPagePaneSlot = (element: Element, container: HTMLElement | null, slots: ReadonlyMap<string, PagePaneSlot>): PagePaneSlot | null => {
    const root = element.closest('.page-pane[data-page-pane-id]');
    if (!root || root.parentElement !== container) return null;
    const slot = slots.get(root.getAttribute('data-page-pane-id') ?? '');
    return slot?.root === root ? slot : null;
};

const requirePagePaneSlot = (pane: RoutePane, slots: ReadonlyMap<string, PagePaneSlot>): PagePaneSlot => {
    const slot = slots.get(pane.id);
    if (!slot || slot.pane !== pane) throw new Error('Pane requires its allocated workspace identity');
    return slot;
};

const allocatePagePaneSlot = (pane: RoutePane, after: RoutePane | null, slots: Map<string, PagePaneSlot>, documentRef: Document): PagePaneSlot => {
    if (after) requirePagePaneSlot(after, slots);
    if (slots.has(pane.id) || slots.size >= 3) throw new Error('Workspace pane allocation exceeds its identity or slot budget');
    const slot = createPagePaneSlot(pane, documentRef, 'opening');
    const entries = [...slots.entries()];
    slots.clear();
    if (after === null) slots.set(pane.id, slot);
    for (const [identity, existing] of entries) {
        slots.set(identity, existing);
        if (existing.pane === after) slots.set(pane.id, slot);
    }
    return slot;
};

const insertPagePaneRoot = (slot: PagePaneSlot, container: HTMLElement, slots: ReadonlyMap<string, PagePaneSlot>): void => {
    const ordered = [...slots.values()];
    const index = ordered.indexOf(slot);
    if (index < 0) throw new Error('Workspace root placement requires its allocated slot');
    const following = ordered.slice(index + 1).find((candidate) => candidate.root.parentElement === container);
    container.insertBefore(slot.root, following?.root ?? null);
};

const getFocusedPageContent = (container: Element): Element | null => (container.classList.contains('page-workspace') ? dom.resolve(':scope > .page-pane[data-pane-focused="true"] > .page-pane-outlet', container) : container);

export { createPagePaneSlot, allocatePagePaneSlot, findPagePaneSlot, requirePagePaneSlot, insertPagePaneRoot, getFocusedPageContent };
