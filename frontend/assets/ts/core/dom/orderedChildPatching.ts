/* SoAI - Shared DOM ordered child patching [frontend/assets/ts/core/dom/orderedChildPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isWhitespaceTextNode } from '@core/dom/domEnvironment.ts';

type OrderedChildPatchArguments<KeyType extends string> = {
    existingParent: HTMLElement;
    createdParent: HTMLElement;
    resolveChildKey: (child: HTMLElement) => KeyType | null;
    insertChild: (parent: HTMLElement, child: HTMLElement, anchor: ChildNode | null) => HTMLElement;
    patchChild: (existingChild: HTMLElement, createdChild: HTMLElement, key: KeyType) => boolean;
    removeChild: (child: HTMLElement) => void;
    replaceUnsupportedChildren: () => boolean;
    isChildDetaching?: (child: HTMLElement) => boolean;
};

type OrderedChildren<KeyType extends string> = {
    childrenByKey: Map<KeyType, HTMLElement>;
    children: HTMLElement[];
};

const isNeverDetaching = (): boolean => false;

const collectOrderedChildren = <KeyType extends string>(parent: HTMLElement, resolveChildKey: (child: HTMLElement) => KeyType | null, isChildDetaching: (child: HTMLElement) => boolean): OrderedChildren<KeyType> | null => {
    const childrenByKey = new Map<KeyType, HTMLElement>();
    const children: HTMLElement[] = [];
    for (const child of Array.from(parent.childNodes)) {
        if (!(child instanceof HTMLElement)) {
            if (isWhitespaceTextNode(child)) {
                continue;
            }
            return null;
        }
        if (isChildDetaching(child)) {
            continue;
        }
        const key = resolveChildKey(child);
        if (key === null || childrenByKey.has(key)) {
            return null;
        }
        childrenByKey.set(key, child);
        children.push(child);
    }
    return { childrenByKey, children };
};

const patchOrderedChildren = <KeyType extends string>(inputArguments: OrderedChildPatchArguments<KeyType>): boolean => {
    const isChildDetaching = inputArguments.isChildDetaching ?? isNeverDetaching;
    const existing = collectOrderedChildren(inputArguments.existingParent, inputArguments.resolveChildKey, isChildDetaching);
    const created = collectOrderedChildren(inputArguments.createdParent, inputArguments.resolveChildKey, isNeverDetaching);
    if (existing === null || created === null) {
        return inputArguments.replaceUnsupportedChildren();
    }
    const pendingRemovals = new Set(Array.from(existing.childrenByKey).flatMap(([key, child]) => (created.childrenByKey.has(key) ? [] : [child])));
    const skipDetachingChildren = (node: ChildNode | null): ChildNode | null => {
        let current = node;
        while (current instanceof HTMLElement && (isChildDetaching(current) || pendingRemovals.has(current))) {
            current = current.nextSibling;
        }
        return current;
    };

    let changed = false;
    let anchor: ChildNode | null = skipDetachingChildren(inputArguments.existingParent.firstChild);
    const seenKeys = new Set<KeyType>();

    for (const createdChild of created.children) {
        const key = inputArguments.resolveChildKey(createdChild);
        if (key === null) {
            return inputArguments.replaceUnsupportedChildren();
        }
        seenKeys.add(key);
        const existingChild = existing.childrenByKey.get(key) ?? null;
        if (!existingChild) {
            const inserted = inputArguments.insertChild(inputArguments.existingParent, createdChild, anchor);
            changed = true;
            anchor = skipDetachingChildren(inserted.nextSibling);
            continue;
        }
        if (anchor !== existingChild) {
            inputArguments.existingParent.insertBefore(existingChild, anchor);
            changed = true;
        }
        anchor = skipDetachingChildren(existingChild.nextSibling);
        if (inputArguments.patchChild(existingChild, createdChild, key)) {
            changed = true;
        }
    }

    for (const [key, existingChild] of existing.childrenByKey.entries()) {
        if (seenKeys.has(key)) {
            continue;
        }
        inputArguments.removeChild(existingChild);
        changed = true;
    }
    return changed;
};

export { patchOrderedChildren };
export type { OrderedChildPatchArguments };
