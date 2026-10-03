/* SoAI - SoAIBench history keyed table row patching [frontend/assets/ts/features/hardware/modals/soaibenchhistory/rowPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { reconcileChildNodes } from '@core/dom/childNodeReconciliation.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { syncElementShell } from '@core/dom/patching.ts';

const STATE_ROW_KEY = 'state';

const resolveHistoryRowKey = (row: HTMLElement): string | null => {
    const runId = row.dataset['runId'];
    if (runId) return `run:${runId}`;
    return row.dataset['historyState'] === undefined ? null : STATE_ROW_KEY;
};

const createHistoryStateRow = (documentRef: Document, colSpan: number, className: string, text: string): HTMLTableRowElement => {
    const row = documentRef.createElement('tr');
    row.dataset['historyState'] = '';
    const cell = documentRef.createElement('td');
    cell.colSpan = colSpan;
    cell.className = className;
    cell.textContent = text;
    row.appendChild(cell);
    return row;
};

const patchHistoryRow = (target: HTMLElement, source: HTMLElement): boolean => {
    if (target.outerHTML === source.outerHTML) return false;
    syncElementShell({ target, source });
    reconcileChildNodes(target, Array.from(source.childNodes));
    return true;
};

const patchHistoryTableRows = (body: HTMLTableSectionElement, rows: readonly HTMLTableRowElement[]): void => {
    const createdParent = body.ownerDocument.createElement('tbody');
    createdParent.append(...rows);
    patchOrderedChildren({
        existingParent: body,
        createdParent,
        resolveChildKey: resolveHistoryRowKey,
        insertChild(parent, child, anchor): HTMLElement {
            parent.insertBefore(child, anchor);
            return child;
        },
        patchChild: patchHistoryRow,
        removeChild(child): void {
            child.remove();
        },
        replaceUnsupportedChildren(): boolean {
            body.replaceChildren(...Array.from(createdParent.children));
            return true;
        }
    });
};

export { createHistoryStateRow, patchHistoryTableRows };
