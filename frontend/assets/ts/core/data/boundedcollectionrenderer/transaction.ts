/* SoAI - Bounded collection detached construction and atomic DOM commit [frontend/assets/ts/core/data/boundedcollectionrenderer/transaction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { addRootScroll, resetRootScroll, resolveCollectionScrollRoot } from '@core/data/boundedcollectionrenderer/scrollRoot.ts';
import type { CollectionBuild, CollectionCommitAnchor, CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/types.ts';
import { dom } from '@core/dom/dom.ts';

interface FocusTarget {
    collectionId: string;
    controlKey: string | null;
    selectionEnd: number | null;
    selectionStart: number | null;
    value: string | null;
}

const findExistingNode = (container: HTMLElement, identifier: string): HTMLElement | null => {
    for (const child of container.children) {
        if (child instanceof HTMLElement && child.dataset['collectionId'] === identifier) return child;
    }
    return null;
};

const indexExistingCollectionNodes = (container: HTMLElement): ReadonlyMap<string, HTMLElement> => {
    const indexed = new Map<string, HTMLElement>();
    for (const child of container.children) {
        if (!(child instanceof HTMLElement)) continue;
        const identifier = child.dataset['collectionId'];
        if (identifier !== undefined) indexed.set(identifier, child);
    }
    return indexed;
};

const createPlannedNode = <TItem>(build: CollectionBuild<TItem>, index: number, renderItem: (item: TItem, context: { id: string }) => HTMLElement, resolveItemIdentifier: (element: HTMLElement) => string | null, requiredTagName: string | null): HTMLElement => {
    const identifier = build.ids[index];
    if (identifier === undefined) throw new Error('Collection build index is outside the validated sequence');
    const existing = build.existingNodes.get(identifier) ?? null;
    if (existing !== null && !build.dirtyIds.has(identifier)) return existing;
    const item = build.lookup.get(identifier);
    if (item === undefined) throw new Error(`Collection lookup is missing identifier during build: ${identifier}`);
    const rendered = renderItem(item, { id: identifier });
    if (!(rendered instanceof HTMLElement)) throw new Error(`Collection renderer must return an HTMLElement for ${identifier}`);
    if (requiredTagName !== null && rendered.tagName !== requiredTagName) throw new Error(`Collection renderer returned ${rendered.tagName} instead of ${requiredTagName} for ${identifier}`);
    const domainIdentifier = resolveItemIdentifier(rendered);
    if (domainIdentifier !== identifier) throw new Error(`Collection renderer identity mismatch for ${identifier}`);
    rendered.dataset['collectionId'] = identifier;
    if (existing === null) build.enteringElements.push(rendered);
    return rendered;
};

const captureViewportAnchor = (container: HTMLElement, survivingNodes: ReadonlySet<HTMLElement> | null = null): CollectionCommitAnchor | null => {
    const root = resolveCollectionScrollRoot(container);
    const viewportTop = root instanceof HTMLElement ? measureLayoutBox(root).top : 0;
    for (const child of container.children) {
        if (!(child instanceof HTMLElement) || child.dataset['collectionId'] === undefined) continue;
        if (survivingNodes !== null && !survivingNodes.has(child)) continue;
        const rectangle = measureLayoutBox(child);
        if (rectangle.bottom <= viewportTop) continue;
        return { element: child, offset: rectangle.top - viewportTop };
    }
    return null;
};

const restoreViewportAnchor = (container: HTMLElement, anchor: CollectionCommitAnchor): void => {
    const identifier = anchor.element.dataset['collectionId'];
    const anchoredElement = anchor.element.isConnected ? anchor.element : identifier === undefined ? null : findExistingNode(container, identifier);
    if (anchoredElement === null) return;
    const root = resolveCollectionScrollRoot(container);
    const viewportTop = root instanceof HTMLElement ? measureLayoutBox(root).top : 0;
    addRootScroll(root, measureLayoutBox(anchoredElement).top - viewportTop - anchor.offset);
};

const restoreKeyedViewportAnchor = (container: HTMLElement, anchor: CollectionViewportAnchor): void => {
    const root = resolveCollectionScrollRoot(container);
    if (anchor.atStart) {
        resetRootScroll(root);
        return;
    }
    for (const child of container.children) {
        if (!(child instanceof HTMLElement) || child.dataset['collectionId'] !== anchor.identifier) continue;
        const viewportTop = root instanceof HTMLElement ? measureLayoutBox(root).top : 0;
        addRootScroll(root, measureLayoutBox(child).top - viewportTop - anchor.offset);
        return;
    }
};

const captureFocus = (container: HTMLElement): FocusTarget | null => {
    const activeElement = container.ownerDocument.activeElement;
    if (!(activeElement instanceof HTMLElement) || !container.contains(activeElement)) return null;
    const collectionElement = activeElement.closest<HTMLElement>('[data-collection-id]');
    const collectionId = collectionElement?.dataset['collectionId'];
    if (collectionId === undefined) return null;
    const controlKey = activeElement.dataset['action'] ?? activeElement.dataset['attachmentOverflowAction'] ?? activeElement.dataset['collectionFocusKey'] ?? null;
    const textControl = activeElement instanceof HTMLInputElement || activeElement instanceof HTMLTextAreaElement ? activeElement : null;
    return { collectionId, controlKey, selectionEnd: textControl?.selectionEnd ?? null, selectionStart: textControl?.selectionStart ?? null, value: textControl?.value ?? null };
};

const restoreFocus = (container: HTMLElement, focusTarget: FocusTarget | null): void => {
    if (focusTarget === null) return;
    let collectionElement: HTMLElement | null = null;
    for (const child of container.children) {
        if (child instanceof HTMLElement && child.dataset['collectionId'] === focusTarget.collectionId) collectionElement = child;
    }
    if (collectionElement === null) {
        const fallbackCandidate = dom.resolve('[data-collection-id]', container);
        const fallback = fallbackCandidate instanceof HTMLElement ? fallbackCandidate : null;
        const controlCandidate = fallback === null ? null : dom.resolve('button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])', fallback);
        const fallbackControl = controlCandidate instanceof HTMLElement ? controlCandidate : fallback;
        fallbackControl?.focus({ preventScroll: true });
        return;
    }
    if (focusTarget.controlKey === null) {
        collectionElement.focus({ preventScroll: true });
        return;
    }
    for (const control of dom.resolveAll('[data-action], [data-attachment-overflow-action], [data-collection-focus-key]', collectionElement)) {
        if (!(control instanceof HTMLElement)) continue;
        const controlKey = control.dataset['action'] ?? control.dataset['attachmentOverflowAction'] ?? control.dataset['collectionFocusKey'] ?? null;
        if (controlKey === focusTarget.controlKey) {
            if ((control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement) && focusTarget.value !== null) {
                control.value = focusTarget.value;
                if (focusTarget.selectionStart !== null && focusTarget.selectionEnd !== null) control.setSelectionRange(focusTarget.selectionStart, focusTarget.selectionEnd);
            }
            control.focus({ preventScroll: true });
            return;
        }
    }
    collectionElement.focus({ preventScroll: true });
};

const commitPlannedNodes = <TItem>(build: CollectionBuild<TItem>): void => {
    const oldChildren = Array.from(build.container.childNodes);
    const survivingNodes = new Set(build.plannedNodes);
    const anchor = captureViewportAnchor(build.container, survivingNodes) ?? captureViewportAnchor(build.container);
    const focusTarget = captureFocus(build.container);
    try {
        for (const child of Array.from(build.container.childNodes)) {
            if (!(child instanceof HTMLElement) || !survivingNodes.has(child)) child.remove();
        }
        for (let index = 0; index < build.plannedNodes.length; index += 1) {
            const plannedNode = build.plannedNodes[index];
            if (plannedNode === undefined) throw new Error('Collection commit index is outside the planned sequence');
            const currentNode = build.container.children.item(index);
            if (currentNode !== plannedNode) build.container.insertBefore(plannedNode, currentNode);
        }
    } catch (error) {
        build.container.replaceChildren(...oldChildren);
        throw error;
    }
    if (anchor !== null) restoreViewportAnchor(build.container, anchor);
    restoreFocus(build.container, focusTarget);
};

const createEdgeLoader = (container: HTMLElement, edge: 'backward' | 'forward', label: string): HTMLElement => {
    const content = container.ownerDocument.createElement('div');
    content.className = 'collection-edge-loader-content';
    const spinner = container.ownerDocument.createElement('span');
    spinner.className = 'loading-spinner';
    spinner.setAttribute('aria-hidden', 'true');
    const text = container.ownerDocument.createElement('span');
    text.className = 'loading-text';
    text.textContent = label;
    content.append(spinner, text);
    if (container instanceof HTMLTableSectionElement) {
        const row = container.ownerDocument.createElement('tr');
        const cell = container.ownerDocument.createElement('td');
        const firstRow = dom.resolve('tr', container);
        cell.colSpan = Math.max(1, firstRow?.children.length ?? 1);
        cell.append(content);
        row.append(cell);
        row.dataset['collectionLoader'] = edge;
        row.setAttribute('role', 'status');
        row.setAttribute('aria-live', 'polite');
        return row;
    }
    const loader = container.ownerDocument.createElement('div');
    loader.append(content);
    loader.dataset['collectionLoader'] = edge;
    loader.setAttribute('role', 'status');
    loader.setAttribute('aria-live', 'polite');
    return loader;
};

export { captureViewportAnchor, commitPlannedNodes, createEdgeLoader, createPlannedNode, indexExistingCollectionNodes, restoreKeyedViewportAnchor, restoreViewportAnchor };
