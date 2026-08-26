/* SoAI - Shared DOM actions effects [frontend/assets/ts/core/dom/actions/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isDocumentFragment } from '@core/dom/domEnvironment.ts';
import { isElementNode, isFunction, isNode } from '@core/typeGuards.ts';
import { isTrustedHtml, type TrustedHtml } from '@core/security/public.ts';

import type { DOMContext, DOMTarget } from '@core/dom/types.ts';

const resolveFragmentReference = (fragment: DocumentFragment, reference: DOMTarget): Node | null => {
    if (!isNode(reference)) return null;
    if (isFunction(fragment.contains) && !fragment.contains(reference)) return null;
    return reference;
};

const applyNodesToFragment = (fragment: DOMTarget, nodes: Node[], reference: DOMTarget = null): boolean => {
    if (!isDocumentFragment(fragment)) return false;

    const referenceNode = resolveFragmentReference(fragment, reference);
    nodes.forEach((node) => {
        if (!isNode(node)) return;
        if (referenceNode) {
            fragment.insertBefore(node, referenceNode);
        } else {
            fragment.appendChild(node);
        }
    });
    return true;
};

const replaceResolvedElement = (resolve: (target: DOMTarget, context?: DOMContext) => Element | null, createFragment: (html?: TrustedHtml) => DocumentFragment, target: DOMTarget, newContent: TrustedHtml | Node, context: DOMContext = null): Element | null => {
    const element = resolve(target, context);
    if (!element || !element.parentNode) return null;

    let replacement: Node;
    if (isTrustedHtml(newContent)) {
        const fragment = createFragment(newContent);
        const firstElement = fragment.firstElementChild;
        if (firstElement) {
            replacement = firstElement;
        } else {
            const firstChild = fragment.firstChild;
            if (!firstChild) return null;
            replacement = firstChild;
        }
    } else if (isNode(newContent)) {
        replacement = newContent;
    } else {
        return null;
    }

    element.parentNode.replaceChild(replacement, element);
    return isElementNode(replacement) ? replacement : null;
};

const querySelectorFromTarget = (resolve: (target: DOMTarget, context?: DOMContext) => Element | null, parent: DOMTarget, selector: string): Element | null => {
    const parentElement = resolve(parent);
    if (!parentElement || !selector) return null;
    return resolve(selector, parentElement);
};

const querySelectorAllFromTarget = (resolve: (target: DOMTarget, context?: DOMContext) => Element | null, resolveAll: (targets: DOMTarget | DOMTarget[], context?: DOMContext) => Element[], parent: DOMTarget, selector: string): Element[] => {
    const parentElement = resolve(parent);
    if (!parentElement || !selector) return [];
    return resolveAll(selector, parentElement);
};

export { applyNodesToFragment, querySelectorAllFromTarget, querySelectorFromTarget, replaceResolvedElement };
