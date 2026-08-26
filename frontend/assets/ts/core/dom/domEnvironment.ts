/* SoAI - Shared DOM environment [frontend/assets/ts/core/dom/domEnvironment.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getGlobalScope } from '@core/environment/public.ts';
import { isElementNode, isFunction, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import type { GlobalScopeType } from '@core/environment/globalScope.ts';
import type { DOMRuntimeCandidate } from '@core/dom/types.ts';

const SVG_NAMESPACE = 'http://www.w3.org/2000/svg';
const TEXT_NODE_TYPE = 3;

interface DomEnvironment {
    scope: GlobalScopeType;
    window: Window;
    document: Document;
}

interface WindowCandidate {
    window?: Window | null | undefined;
    document?: Document | null | undefined;
}

interface DocumentCandidate {
    nodeType?: number;
    getElementById?: (id: string) => HTMLElement | null;
}

interface DocumentFragmentCandidate {
    nodeType?: number;
    querySelector?: (selectors: string) => Element | null;
    querySelectorAll?: (selectors: string) => NodeListOf<Element>;
}

interface ElementCandidate {
    nodeType?: number;
    matches?: (selectors: string) => boolean;
    querySelector?: (selectors: string) => Element | null;
    querySelectorAll?: (selectors: string) => NodeListOf<Element>;
    ownerDocument?: Document | null | undefined;
}

const hasWindowFields = <T>(value: T): value is T & WindowCandidate => isObject(value) && 'window' in value && 'document' in value;

const hasDocumentFields = <T>(value: T): value is T & DocumentCandidate => isObject(value) && 'nodeType' in value;

const hasDocumentFragmentFields = <T>(value: T): value is T & DocumentFragmentCandidate => isObject(value) && 'nodeType' in value;

const hasElementFields = <T>(value: T): value is T & ElementCandidate => isObject(value) && 'nodeType' in value;

function isWindow(value: DOMRuntimeCandidate): value is Window {
    if (!hasWindowFields(value)) return false;
    const self = value.window;
    if (self !== value) return false;
    return isDocument(value.document);
}

function isDocument(value: DOMRuntimeCandidate): value is Document {
    if (!hasDocumentFields(value)) return false;
    const nodeType = value.nodeType;
    if (nodeType !== 9) return false;
    return isFunction(value.getElementById);
}

function isDocumentFragment(value: DOMRuntimeCandidate): value is DocumentFragment {
    if (!hasDocumentFragmentFields(value)) return false;
    const nodeType = value.nodeType;
    if (nodeType !== 11) return false;
    return isFunction(value.querySelector) && isFunction(value.querySelectorAll);
}

function isElementNodeLike(value: DOMRuntimeCandidate): value is Element {
    if (isElementNode(value)) return true;
    if (!hasElementFields(value)) return false;
    const nodeType = value.nodeType;
    if (nodeType !== 1) return false;
    return isFunction(value.matches) && isFunction(value.querySelector) && isFunction(value.querySelectorAll) && isDocument(value.ownerDocument);
}

function isHTMLElementNodeLike(value: DOMRuntimeCandidate): value is HTMLElement {
    if (!isElementNodeLike(value)) return false;
    const ctor = value.ownerDocument.defaultView?.HTMLElement ?? null;
    return ctor !== null && value instanceof ctor;
}

const isWhitespaceTextNode = (node: ChildNode): boolean => node.nodeType === TEXT_NODE_TYPE && (node.textContent ?? '').trim().length === 0;

const createDomEnvironment = (scopeCandidate: GlobalScopeType | null | undefined = getGlobalScope()): DomEnvironment => {
    if (!isObject(scopeCandidate)) throw new Error('globalThis is required for DOM operations');
    if (!hasWindowFields(scopeCandidate)) throw new Error('window global is required for DOM operations');
    const windowValue: DOMRuntimeCandidate = scopeCandidate.window;
    if (!isWindow(windowValue)) throw new Error('window global is required for DOM operations');
    return {
        scope: scopeCandidate,
        window: windowValue,
        document: windowValue.document
    };
};

let domEnvironment: DomEnvironment | null = null;

const ensureDomEnvironment = (): DomEnvironment => {
    if (!domEnvironment) {
        domEnvironment = createDomEnvironment(getGlobalScope());
    }
    return domEnvironment;
};

const initializeDomEnvironment = (scopeCandidate: GlobalScopeType | null | undefined = getGlobalScope()): DomEnvironment => {
    domEnvironment = createDomEnvironment(scopeCandidate);
    return domEnvironment;
};

const getDomWindow = (): Window => ensureDomEnvironment().window;
const getDomDocument = (): Document => ensureDomEnvironment().document;

const isElement = (value: DOMRuntimeCandidate): value is Element | Document | Window => !isNullOrUndefined(value) && (isWindow(value) || isDocument(value) || isElementNodeLike(value));

export { SVG_NAMESPACE, createDomEnvironment, getDomDocument, getDomWindow, initializeDomEnvironment, isDocument, isDocumentFragment, isElement, isElementNodeLike, isHTMLElementNodeLike, isWhitespaceTextNode, isWindow };
export type { DomEnvironment };
