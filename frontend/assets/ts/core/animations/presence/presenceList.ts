/* SoAI - Presence-animated keyed list reconciliation with stable row striping [frontend/assets/ts/core/animations/presence/presenceList.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, removeWithPresence } from '@core/animations/presence/presenceDom.ts';
import { isRendered } from '@core/animations/presence/presenceGeometry.ts';
import { deferUntilPresenceExitsSettle } from '@core/animations/presence/presenceMotion.ts';
import { isPresenceExiting } from '@core/animations/presence/presenceTransitions.ts';
import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { CHECKERBOARD_CLASS_NAMES, syncStableCheckerboardClasses } from '@core/dom/checkerboardAssignment.ts';
import { createHtmlFragment } from '@core/dom/html.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import type { TrustedHtml } from '@core/security/public.ts';

interface PresenceListReconcileArguments {
    list: HTMLElement;
    rowsHtml: TrustedHtml;
    emptyStateHtml: TrustedHtml;
    resolveRowKey: (row: HTMLElement) => string | null;
}

const MAX_ANIMATED_INSERTIONS = 3;
const populatedLists = new WeakSet<HTMLElement>();

const canAnimateListInsertions = (list: HTMLElement): boolean => populatedLists.has(list) && isRendered(list);

const parseListChildren = (list: HTMLElement, html: TrustedHtml): HTMLElement => {
    const parent = list.ownerDocument.createElement('div');
    parent.appendChild(createHtmlFragment({ documentRef: list.ownerDocument, html: html.html, context: list }));
    return parent;
};

const resolveSettledChildren = (list: HTMLElement): HTMLElement[] => Array.from(list.children).filter((child): child is HTMLElement => child instanceof HTMLElement && !isPresenceExiting(child));

const patchListRow = (existingRow: HTMLElement, createdRow: HTMLElement): boolean => {
    let changed = syncElementShell({ target: existingRow, source: createdRow, preservedClassNames: CHECKERBOARD_CLASS_NAMES });
    if (existingRow.innerHTML !== createdRow.innerHTML) {
        reconcileChildNodes(existingRow, Array.from(createdRow.childNodes));
        changed = true;
    }
    return changed;
};

const showEmptyState = (inputArguments: PresenceListReconcileArguments, animate: boolean): void => {
    const { list, resolveRowKey } = inputArguments;
    const emptyState = parseListChildren(list, inputArguments.emptyStateHtml).firstElementChild;
    if (!(emptyState instanceof HTMLElement)) {
        throw new Error('Presence list empty state markup must render one element');
    }
    const settledChildren = resolveSettledChildren(list);
    for (const child of settledChildren) {
        if (resolveRowKey(child) !== null) removeWithPresence(child);
    }
    const existingEmptyState = settledChildren.find((child) => resolveRowKey(child) === null);
    if (existingEmptyState) {
        patchListRow(existingEmptyState, emptyState);
        return;
    }
    const insertEmptyState = (): void => {
        if (resolveSettledChildren(list).length === 0) insertWithPresence(list, emptyState, null, animate);
    };
    const lastExitingChild = Array.from(list.children)
        .reverse()
        .find((child): child is HTMLElement => child instanceof HTMLElement && isPresenceExiting(child));
    if (!lastExitingChild || !deferUntilPresenceExitsSettle(lastExitingChild, insertEmptyState)) insertEmptyState();
};

const reconcilePresenceList = (inputArguments: PresenceListReconcileArguments): void => {
    const { list, resolveRowKey } = inputArguments;
    const createdParent = parseListChildren(list, inputArguments.rowsHtml);
    const animate = canAnimateListInsertions(list);
    populatedLists.add(list);
    if (createdParent.childElementCount === 0) {
        showEmptyState(inputArguments, animate);
        return;
    }
    const settledKeys = new Set<string>();
    for (const child of resolveSettledChildren(list)) {
        const key = resolveRowKey(child);
        if (key === null) removeWithPresence(child);
        else settledKeys.add(key);
    }
    const insertedRowCount = Array.from(createdParent.children).filter((child) => child instanceof HTMLElement && !settledKeys.has(resolveRowKey(child) ?? '')).length;
    const animateInsertions = animate && insertedRowCount <= MAX_ANIMATED_INSERTIONS;
    let listBounds: { top: number; bottom: number } | null = null;
    const removeListRow = (row: HTMLElement): void => {
        listBounds ??= measureLayoutBox(list);
        const rowBounds = measureLayoutBox(row);
        if (rowBounds.bottom > listBounds.top && rowBounds.top < listBounds.bottom) removeWithPresence(row);
        else row.remove();
    };
    patchOrderedChildren({
        existingParent: list,
        createdParent,
        resolveChildKey: resolveRowKey,
        insertChild(parent, row, anchor): HTMLElement {
            insertWithPresence(parent, row, anchor, animateInsertions);
            return row;
        },
        patchChild: patchListRow,
        removeChild: removeListRow,
        replaceUnsupportedChildren(): boolean {
            list.replaceChildren(...Array.from(createdParent.children));
            return true;
        },
        isChildDetaching: isPresenceExiting
    });
    syncStableCheckerboardClasses(resolveSettledChildren(list));
};

export { reconcilePresenceList };
export type { PresenceListReconcileArguments };
