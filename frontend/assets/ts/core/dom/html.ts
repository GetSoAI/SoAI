/* SoAI - Shared DOM HTML [frontend/assets/ts/core/dom/html.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isDocument, isElementNodeLike, isHTMLElementNodeLike } from '@core/dom/domEnvironment.ts';
import { isString } from '@core/typeGuards.ts';

import type { TrustedHtml } from '@core/security/public.ts';

const resolveHtmlContextElement = (documentRef: Document, context: Element | Document | null): Element => {
    if (isElementNodeLike(context)) {
        return context;
    }
    const doc = isDocument(context) ? context : documentRef;
    const element = doc.body ?? doc.documentElement;
    if (!element) {
        throw new Error('HTML parsing requires a document element');
    }
    return element;
};

const createHtmlFragment = (inputArguments: { documentRef: Document; html: string; context?: Element | Document | null }): DocumentFragment => {
    const { documentRef, html, context = null } = inputArguments;
    const normalized = isString(html) ? html : '';
    if (!normalized) {
        return documentRef.createDocumentFragment();
    }

    const contextElement = resolveHtmlContextElement(documentRef, context);
    const range = documentRef.createRange();
    range.selectNodeContents(contextElement);
    return range.createContextualFragment(normalized);
};

const createInertHtmlParser = (documentRef: Document): ((markup: string, checkpoint: () => Promise<void>) => Promise<HTMLElement>) => {
    const inertDocument = documentRef.implementation.createHTMLDocument('');
    return async (markup, checkpoint) => {
        await checkpoint();
        inertDocument.open();
        try {
            inertDocument.write('<!doctype html><html><head></head><body>');
            for (let offset = 0; offset < markup.length; offset += 8192) {
                await checkpoint();
                inertDocument.write(markup.slice(offset, offset + 8192));
            }
        } finally {
            inertDocument.close();
        }
        if (!inertDocument.body) throw new Error('Inert HTML parsing did not create a body');
        return inertDocument.body;
    };
};

const createHtmlTableRow = (inputArguments: { documentRef: Document; html: TrustedHtml; context?: HTMLTableSectionElement | null }): HTMLTableRowElement => {
    const context = inputArguments.context ?? inputArguments.documentRef.createElement('tbody');
    const fragment = createHtmlFragment({
        documentRef: inputArguments.documentRef,
        html: inputArguments.html.html,
        context
    });
    const row = fragment.firstElementChild;
    if (!(row instanceof HTMLTableRowElement) || fragment.childElementCount !== 1) {
        throw new Error('Table row markup must contain exactly one table row');
    }
    return row;
};

const replaceChildrenFromHtml = (inputArguments: { element: Element; html: string; context?: Element | Document | null }): void => {
    const { element, html, context = null } = inputArguments;
    const fragment = createHtmlFragment({ documentRef: element.ownerDocument, html, context: context ?? element });
    if (isHTMLElementNodeLike(element) && typeof element.replaceChildren === 'function') {
        element.replaceChildren(fragment);
        return;
    }
    element.textContent = '';
    element.appendChild(fragment);
};

const replaceChildrenFromTrustedHtml = (inputArguments: { element: Element; html: TrustedHtml; context?: Element | Document | null }): void => {
    const context = inputArguments.context;
    if (context === undefined) {
        replaceChildrenFromHtml({ element: inputArguments.element, html: inputArguments.html.html });
        return;
    }
    replaceChildrenFromHtml({ element: inputArguments.element, html: inputArguments.html.html, context });
};

const serializeNodeToHtml = (node: Node): string => {
    const documentRef = node.ownerDocument;
    if (documentRef === null) {
        throw new Error('HTML serialization requires a node owned by a document');
    }
    const template = documentRef.createElement('template');
    template.content.append(node.cloneNode(true));
    return template.innerHTML;
};

const serializeElementToHtml = (element: Element): string => serializeNodeToHtml(element);

const serializeElementChildrenToHtml = (element: Element): string => Array.from(element.childNodes, serializeNodeToHtml).join('');

const insertHtmlBefore = (inputArguments: { reference: Element; html: string; context?: Element | Document | null }): void => {
    const { reference, html, context = null } = inputArguments;
    const fragment = createHtmlFragment({ documentRef: reference.ownerDocument, html, context: context ?? reference });
    reference.before(fragment);
};

const appendHtml = (inputArguments: { element: Element; html: string; context?: Element | Document | null }): void => {
    const { element, html, context = null } = inputArguments;
    const fragment = createHtmlFragment({ documentRef: element.ownerDocument, html, context: context ?? element });
    element.appendChild(fragment);
};

export { appendHtml, createHtmlFragment, createHtmlTableRow, createInertHtmlParser, insertHtmlBefore, replaceChildrenFromHtml, replaceChildrenFromTrustedHtml, serializeElementChildrenToHtml, serializeElementToHtml, serializeNodeToHtml };
