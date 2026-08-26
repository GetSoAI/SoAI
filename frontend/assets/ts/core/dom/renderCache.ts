/* SoAI - Shared DOM render cache [frontend/assets/ts/core/dom/renderCache.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isDocumentFragment } from '@core/dom/domEnvironment.ts';
import { isArray, isElementNode, isFunction, isNode } from '@core/typeGuards.ts';

type NodeUnlike = Node | DocumentFragment;
type RenderNodeInput = NodeUnlike | readonly (NodeUnlike | null)[] | null;

const renderCache = new WeakMap<Element, string>();

const isNodeUnlike = (value: NodeUnlike | null): value is NodeUnlike => Boolean(value) && (isNode(value) || isDocumentFragment(value));

const toNodeArray = (value: RenderNodeInput): Node[] => {
    if (!value) return [];
    if (isArray(value)) {
        const nodes: Node[] = [];
        for (const entry of value) {
            if (isNodeUnlike(entry)) nodes.push(entry);
        }
        return nodes;
    }
    return isNodeUnlike(value) ? [value] : [];
};

const buildFragment = (nodes: readonly (NodeUnlike | null)[] = []): DocumentFragment => dom.createFragmentFromNodes(toNodeArray(nodes));

const ensureElement = (target: Element | null): Element => {
    if (isElementNode(target)) return target;
    throw new Error('Render target must be an element');
};

const renderCachedContent = (target: Element | null, cacheKey: string | null, builder: () => RenderNodeInput): Element => {
    if (!isFunction(builder)) throw new Error('Render builder must be a function');
    const element = ensureElement(target);
    if (cacheKey !== null && renderCache.get(element) === cacheKey) return element;
    const nodes = builder();
    const resolved = toNodeArray(nodes);
    element.replaceChildren(...resolved);
    if (cacheKey !== null) renderCache.set(element, cacheKey);
    else renderCache.delete(element);
    return element;
};

export { renderCachedContent, toNodeArray, buildFragment };
