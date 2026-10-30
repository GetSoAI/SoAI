/* SoAI - Shared DOM child node reconciliation [frontend/assets/ts/core/dom/childNodeReconciliation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyTextContent, isFadingTextTarget } from '@core/dom/textContent.ts';
import { syncElementShell } from '@core/dom/patching.ts';
import { createHtmlFragment } from '@core/dom/html.ts';
import type { TrustedHtml } from '@core/security/public.ts';

const repeatedReconcileMarkupByTarget = new WeakMap<Element, { html: string; markup: string }>();

interface ChildReconciliationOptions {
    preservedClassNames?: ReadonlySet<string>;
    preservedAttributeNames?: ReadonlySet<string>;
}

const syncElementAttributes = (target: Element, source: Element, options?: ChildReconciliationOptions): boolean => {
    if (options && target instanceof HTMLElement && source instanceof HTMLElement) {
        return syncElementShell({ target, source, ...options });
    }
    let changed = false;
    for (let index = target.attributes.length - 1; index >= 0; index -= 1) {
        const attr = target.attributes[index];
        if (attr && !source.hasAttribute(attr.name)) {
            target.removeAttribute(attr.name);
            changed = true;
        }
    }
    for (let index = 0; index < source.attributes.length; index += 1) {
        const attr = source.attributes[index];
        if (attr && target.getAttribute(attr.name) !== attr.value) {
            target.setAttribute(attr.name, attr.value);
            changed = true;
        }
    }
    return changed;
};

const canPatchInPlace = (target: ChildNode | null | undefined, source: ChildNode | null | undefined): boolean => {
    if (!target || !source || target.nodeType !== source.nodeType) {
        return false;
    }
    if (target.nodeType === Node.TEXT_NODE) {
        return true;
    }
    return target instanceof Element && source instanceof Element && target.tagName === source.tagName;
};

const reconcileChildNodes = (targetParent: Element, sourceNodes: ReadonlyArray<ChildNode>, options?: ChildReconciliationOptions): boolean => {
    if (isFadingTextTarget(targetParent) && sourceNodes.every((node) => node.nodeType === Node.TEXT_NODE)) {
        return applyTextContent(targetParent, sourceNodes.map((node) => node.textContent ?? '').join(''));
    }
    let changed = false;
    let targetChild: ChildNode | null = targetParent.firstChild;
    let sourceIndex = 0;

    while (sourceIndex < sourceNodes.length) {
        const sourceNode = sourceNodes[sourceIndex];
        if (!sourceNode) {
            sourceIndex += 1;
            continue;
        }
        if (!targetChild) {
            targetParent.appendChild(sourceNode);
            changed = true;
            sourceIndex += 1;
            continue;
        }
        if (canPatchInPlace(targetChild, sourceNode)) {
            changed = applyChildPatch(targetChild, sourceNode, options) || changed;
            targetChild = targetChild.nextSibling;
            sourceIndex += 1;
            continue;
        }
        const nextSourceNode = sourceNodes[sourceIndex + 1];
        if (canPatchInPlace(targetChild, nextSourceNode) && targetChild.isEqualNode(nextSourceNode ?? null)) {
            targetParent.insertBefore(sourceNode, targetChild);
            changed = true;
            sourceIndex += 1;
            continue;
        }
        const nextTarget = targetChild.nextSibling;
        if (canPatchInPlace(nextTarget, sourceNode) && nextTarget?.isEqualNode(sourceNode)) {
            targetChild.remove();
            changed = true;
            targetChild = nextTarget;
            continue;
        }
        targetChild.replaceWith(sourceNode);
        changed = true;
        targetChild = nextTarget;
        sourceIndex += 1;
    }

    while (targetChild) {
        const nextTarget = targetChild.nextSibling;
        targetChild.remove();
        changed = true;
        targetChild = nextTarget;
    }
    return changed;
};

const applyChildPatch = (target: Node, source: Node, options?: ChildReconciliationOptions): boolean => {
    if (target.nodeType !== source.nodeType) {
        throw new Error('applyChildPatch requires matching node types');
    }
    if (target.nodeType === Node.TEXT_NODE) {
        if (target.textContent !== source.textContent) {
            target.textContent = source.textContent;
            return true;
        }
        return false;
    }
    if (target.nodeType !== Node.ELEMENT_NODE) {
        return false;
    }
    if (!(target instanceof Element) || !(source instanceof Element)) {
        return false;
    }
    if (target.tagName !== source.tagName) {
        target.replaceWith(source);
        return true;
    }
    const attributesChanged = syncElementAttributes(target, source, options);
    const childrenChanged = reconcileChildNodes(target, Array.from(source.childNodes), options);
    return attributesChanged || childrenChanged;
};

const reconcileElementChildrenFromHtml = (inputArguments: { target: Element; html: string; context?: Element | Document | null }): void => {
    const fragment = createHtmlFragment({ documentRef: inputArguments.target.ownerDocument, html: inputArguments.html, context: inputArguments.context ?? inputArguments.target });
    reconcileChildNodes(inputArguments.target, Array.from(fragment.childNodes));
};

const reconcileElementChildrenFromTrustedHtml = (inputArguments: { target: Element; html: TrustedHtml; context?: Element | Document | null }): void => {
    if (inputArguments.context === undefined) {
        reconcileElementChildrenFromHtml({ target: inputArguments.target, html: inputArguments.html.html });
        return;
    }
    reconcileElementChildrenFromHtml({ target: inputArguments.target, html: inputArguments.html.html, context: inputArguments.context });
};

const reconcileRepeatedElementChildrenFromTrustedHtml = (inputArguments: { target: Element; html: TrustedHtml }): void => {
    const previous = repeatedReconcileMarkupByTarget.get(inputArguments.target);
    if (previous !== undefined && previous.html === inputArguments.html.html && previous.markup === inputArguments.target.innerHTML) {
        return;
    }
    reconcileElementChildrenFromTrustedHtml({ target: inputArguments.target, html: inputArguments.html });
    repeatedReconcileMarkupByTarget.set(inputArguments.target, { html: inputArguments.html.html, markup: inputArguments.target.innerHTML });
};

export { reconcileChildNodes, reconcileElementChildrenFromHtml, reconcileElementChildrenFromTrustedHtml, reconcileRepeatedElementChildrenFromTrustedHtml };
