/* SoAI - Settings feature row patching [frontend/assets/ts/features/settings/externalaccounts/rowPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { replaceChildrenFromHtml } from '@core/dom/html.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { parseSingleRootElement } from '@core/dom/parseSingleRootElement.ts';
import { replaceChildrenIfChanged, syncElementShell } from '@core/dom/patching.ts';
import { securityApi, toTrustedHtml } from '@core/security/public.ts';

const createTemplateRow = (documentRef: Document, markup: string): HTMLElement => {
    const sanitizedMarkup = securityApi.sanitizeHtml(markup.trim());
    const element = parseSingleRootElement({
        documentRef,
        html: toTrustedHtml(sanitizedMarkup),
        context: documentRef
    });
    if (element === null) {
        throw new Error('External accounts row markup is invalid');
    }
    return element;
};

const patchRowElement = (target: HTMLElement, source: HTMLElement): boolean => {
    if (target.outerHTML === source.outerHTML) {
        return false;
    }
    syncElementShell({ target, source });
    replaceChildrenIfChanged(target, source);
    return true;
};

const createRowsParent = (container: HTMLElement, rows: ReadonlyArray<{ key: string; markup: string }>): HTMLElement => {
    const parent = container.ownerDocument.createElement('div');
    rows.forEach((row) => {
        const element = createTemplateRow(container.ownerDocument, row.markup);
        if (resolveRowKey(element) !== row.key) {
            throw new Error('External accounts row key does not match rendered account id');
        }
        parent.appendChild(element);
    });
    return parent;
};

const resolveRowKey = (child: HTMLElement): string | null => optionalTrimmedDataAttribute(child, 'account-id') ?? null;

const replaceUnsupportedRows = (container: HTMLElement, createdParent: HTMLElement): boolean => {
    container.replaceChildren(...Array.from(createdParent.children));
    return true;
};

const patchKeyedRows = (container: HTMLElement, rows: ReadonlyArray<{ key: string; markup: string }>, emptyMarkup: string): void => {
    if (rows.length === 0) {
        replaceChildrenFromHtml({
            element: container,
            html: securityApi.sanitizeHtml(emptyMarkup),
            context: container
        });
        return;
    }
    const createdParent = createRowsParent(container, rows);
    patchOrderedChildren({
        existingParent: container,
        createdParent,
        resolveChildKey: resolveRowKey,
        insertChild(parent, child, anchor): HTMLElement {
            parent.insertBefore(child, anchor);
            return child;
        },
        patchChild(existingChild, createdChild): boolean {
            return patchRowElement(existingChild, createdChild);
        },
        removeChild(child): void {
            child.remove();
        },
        replaceUnsupportedChildren(): boolean {
            return replaceUnsupportedRows(container, createdParent);
        }
    });
};

export { patchKeyedRows };
