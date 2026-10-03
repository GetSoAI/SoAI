/* SoAI - Shared DOM resolver [frontend/assets/ts/core/dom/domResolver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isDocument, isDocumentFragment, isElement, isElementNodeLike, isHTMLElementNodeLike, isWindow } from '@core/dom/domEnvironment.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ensureArray } from '@core/normalize.ts';
import { isFunction, isString } from '@core/typeGuards.ts';

import type { DomResolver, DomResolverApi, DomResolverDependencies } from '@core/dom/actions/types.ts';
import type { DOMContext, DOMQueryRoot, DOMTarget } from '@core/dom/types.ts';

const normalizeContext = (context: DOMContext, getDoc: () => Document): DOMQueryRoot => {
    if (context) {
        if (isDocument(context)) return context;
        if (isElementNodeLike(context)) return context;
        if (isDocumentFragment(context)) return context;
    }
    return getDoc();
};

const tryReadSimpleIdSelector = (selector: string): string | null => {
    if (!selector || selector[0] !== '#') {
        return null;
    }
    if (!/^#[A-Za-z0-9_.:-]+$/.test(selector)) {
        return null;
    }
    return selector.slice(1);
};

const findDescendantById = (root: Element, id: string): Element | null => {
    const documentCandidate = root.ownerDocument.getElementById(id);
    if (documentCandidate !== null && documentCandidate !== root && root.contains(documentCandidate)) {
        return documentCandidate;
    }
    for (const candidate of root.querySelectorAll('[id]')) {
        if (candidate.getAttribute('id') === id) {
            return candidate;
        }
    }
    return null;
};

const querySafeAll = (context: DOMContext, selector: string | null | undefined, dependencies: DomResolverDependencies): Element[] => {
    if (!selector || !isString(selector)) return [];

    const root = normalizeContext(context, dependencies.getDomDocument);
    try {
        const id = tryReadSimpleIdSelector(selector);
        if (id && isElementNodeLike(root)) {
            const descendant = findDescendantById(root, id);
            return descendant === null ? [] : [descendant];
        }
        return Array.from(root.querySelectorAll(selector));
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('DOM', `Invalid selector: ${selector}`, runtimeError);
        throw runtimeError;
    }
};

const createDomResolver = (dependencies: DomResolverDependencies): DomResolver => {
    const { getDomDocument } = dependencies;

    const querySafe = (selector: string, context?: DOMContext): Element | null => {
        if (!selector || !isString(selector)) return null;

        const root = normalizeContext(context ?? null, getDomDocument);
        try {
            const id = tryReadSimpleIdSelector(selector);
            if (id && isElementNodeLike(root)) {
                return findDescendantById(root, id);
            }
            return root.querySelector(selector);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('DOM', `Invalid selector: ${selector}`, runtimeError);
            throw runtimeError;
        }
    };

    const getUI = (selector: DOMTarget, context?: DOMContext): Element | null => {
        if (!selector) return null;
        if (isElementNodeLike(selector)) return selector;
        const activeContext = context ?? getDomDocument();
        if (!isString(selector)) return null;
        return querySafe(selector, activeContext);
    };

    const resolve = (target: DOMTarget, context?: DOMContext): Element | null => {
        const activeContext = context ?? getDomDocument();
        if (!target) return null;
        if (isElementNodeLike(target)) return target;
        if (isString(target)) return querySafe(target, activeContext);
        return null;
    };

    const resolveAll = (targets: DOMTarget | DOMTarget[], context?: DOMContext): Element[] => {
        const activeContext = context ?? getDomDocument();
        return ensureArray(targets).flatMap((item): Element[] => {
            if (!item) return [];
            if (isElementNodeLike(item)) return [item];
            if (isString(item)) return querySafeAll(activeContext, item, dependencies);
            return [];
        });
    };

    const resolveContainer = (container: HTMLElement | string | null | undefined): HTMLElement | null => {
        const doc = getDomDocument();
        if (isHTMLElementNodeLike(container)) return container;
        if (isString(container)) {
            const byId = doc.getElementById(container);
            if (byId && isHTMLElementNodeLike(byId)) return byId;
            const bySelector = querySafe(container, doc);
            return bySelector && isHTMLElementNodeLike(bySelector) ? bySelector : null;
        }
        return null;
    };

    const apply = (targets: DOMTarget | DOMTarget[], callback: ((element: Element, index: number) => void) | undefined, context?: DOMContext): Element[] => {
        const activeContext = context ?? getDomDocument();
        const elements = resolveAll(targets, activeContext);
        if (isFunction(callback)) {
            elements.forEach((element, index) => {
                callback(element, index);
            });
        }
        return elements;
    };

    const matches = (element: DOMTarget, selector: string): boolean => {
        const node = resolve(element);
        return node?.matches?.(selector) ?? false;
    };

    const closest = (element: DOMTarget, selector: string): Element | null => {
        const node = resolve(element);
        return node?.closest?.(selector) ?? null;
    };

    const domResolverApi: DomResolverApi = {
        ensureArray: <T>(value: T | T[] | null | undefined): T[] => ensureArray(value),
        isElement,
        isDocument,
        isWindow,
        querySafe,
        safeQueryAll: (selector: string, context?: DOMContext): Element[] => querySafeAll(context ?? null, selector, dependencies),
        resolve,
        resolveAll,
        resolveContainer,
        matches,
        closest,
        apply
    };

    return {
        normalizeContext: (context: DOMContext): DOMQueryRoot => normalizeContext(context, getDomDocument),
        querySafe,
        safeQueryAll: (selector: string, context?: DOMContext): Element[] => querySafeAll(context ?? null, selector, dependencies),
        getUI,
        resolve,
        resolveAll,
        resolveContainer,
        matches,
        closest,
        apply,
        domResolverApi
    };
};

export { createDomResolver };
