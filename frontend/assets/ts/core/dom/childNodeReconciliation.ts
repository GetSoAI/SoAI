/* SoAI - Shared DOM child node reconciliation [frontend/assets/ts/core/dom/childNodeReconciliation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHtmlFragment } from '@core/dom/html.ts';
import type { TrustedHtml } from '@core/security/public.ts';

const syncElementAttributes = (target: Element, source: Element): void => {
    for (let index = target.attributes.length - 1; index >= 0; index -= 1) {
        const attr = target.attributes[index];
        if (attr && !source.hasAttribute(attr.name)) {
            target.removeAttribute(attr.name);
        }
    }
    for (let index = 0; index < source.attributes.length; index += 1) {
        const attr = source.attributes[index];
        if (attr && target.getAttribute(attr.name) !== attr.value) {
            target.setAttribute(attr.name, attr.value);
        }
    }
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

const reconcileChildNodes = (targetParent: Element, sourceNodes: ReadonlyArray<ChildNode>): void => {
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
            sourceIndex += 1;
            continue;
        }
        if (canPatchInPlace(targetChild, sourceNode)) {
            applyChildPatch(targetChild, sourceNode);
            targetChild = targetChild.nextSibling;
            sourceIndex += 1;
            continue;
        }
        const nextSourceNode = sourceNodes[sourceIndex + 1];
        if (canPatchInPlace(targetChild, nextSourceNode) && targetChild.isEqualNode(nextSourceNode ?? null)) {
            targetParent.insertBefore(sourceNode, targetChild);
            sourceIndex += 1;
            continue;
        }
        const nextTarget = targetChild.nextSibling;
        if (canPatchInPlace(nextTarget, sourceNode) && nextTarget?.isEqualNode(sourceNode)) {
            targetChild.remove();
            targetChild = nextTarget;
            continue;
        }
        targetChild.replaceWith(sourceNode);
        targetChild = nextTarget;
        sourceIndex += 1;
    }

    while (targetChild) {
        const nextTarget = targetChild.nextSibling;
        targetChild.remove();
        targetChild = nextTarget;
    }
};

const applyChildPatch = (target: Node, source: Node): void => {
    if (target.nodeType !== source.nodeType) {
        throw new Error('applyChildPatch requires matching node types');
    }
    if (target.nodeType === Node.TEXT_NODE) {
        if (target.textContent !== source.textContent) {
            target.textContent = source.textContent;
        }
        return;
    }
    if (target.nodeType !== Node.ELEMENT_NODE) {
        return;
    }
    if (!(target instanceof Element) || !(source instanceof Element)) {
        return;
    }
    if (target.tagName !== source.tagName) {
        target.replaceWith(source);
        return;
    }
    syncElementAttributes(target, source);
    reconcileChildNodes(target, Array.from(source.childNodes));
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

export { reconcileChildNodes, reconcileElementChildrenFromHtml, reconcileElementChildrenFromTrustedHtml };
