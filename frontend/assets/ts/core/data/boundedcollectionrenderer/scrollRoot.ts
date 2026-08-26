/* SoAI - Bounded collection scroll-root discovery and boundary geometry [frontend/assets/ts/core/data/boundedcollectionrenderer/scrollRoot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { measureScrollEdges, normalizeScrollPosition } from '@core/dom/scrollGeometry.ts';
import { getComputedStyleStrict, getDocument, getWindow } from '@core/environment/public.ts';

type CollectionScrollRoot = HTMLElement | Window;

interface CollectionBoundaryMeasurement {
    atStart: boolean;
    atEnd: boolean;
    position: number;
    measurable: boolean;
}

const isScrollableOverflow = (value: string): boolean => /^(auto|overlay|scroll)$/.test(value.trim());

const resolveCollectionScrollRoot = (container: HTMLElement): CollectionScrollRoot => {
    let candidate: HTMLElement | null = container;
    while (candidate !== null) {
        const style = getComputedStyleStrict(candidate);
        if (isScrollableOverflow(style.overflowY)) return candidate;
        candidate = candidate.parentElement;
    }
    return getWindow();
};

const readRootPosition = (root: CollectionScrollRoot): number => {
    if (root instanceof HTMLElement) {
        return normalizeScrollPosition(root.scrollTop, Math.max(0, root.scrollHeight - root.clientHeight));
    }
    const documentElement = getDocument().documentElement;
    return normalizeScrollPosition(root.scrollY, Math.max(0, documentElement.scrollHeight - measureLayoutViewport(documentElement).height));
};

const measureCollectionBoundaries = (container: HTMLElement, root: CollectionScrollRoot): CollectionBoundaryMeasurement => {
    const containerRect = measureLayoutBox(container);
    const rootRect = root instanceof HTMLElement ? measureLayoutBox(root) : null;
    const viewportTop = rootRect === null ? 0 : rootRect.top;
    const viewportHeight = root instanceof HTMLElement ? root.clientHeight : measureLayoutViewport(container).height;
    const viewportBottom = viewportTop + viewportHeight;
    const position = readRootPosition(root);
    if (!container.isConnected || viewportHeight <= 0 || containerRect.width <= 0 || containerRect.height <= 0) {
        return { atStart: false, atEnd: false, position, measurable: false };
    }
    if (root === container) {
        const edges = measureScrollEdges({ position, extent: container.scrollHeight, viewport: container.clientHeight, tolerance: 1 });
        return { atStart: edges.atStart, atEnd: edges.atEnd, position, measurable: true };
    }
    const startDistance = Math.max(0, viewportTop - containerRect.top);
    const endDistance = Math.max(0, containerRect.bottom - viewportBottom);
    const start = measureScrollEdges({ position: startDistance, extent: startDistance + viewportHeight, viewport: viewportHeight, tolerance: 1 });
    const end = measureScrollEdges({ position: endDistance, extent: endDistance + viewportHeight, viewport: viewportHeight, tolerance: 1 });
    return { atStart: start.atStart, atEnd: end.atStart, position, measurable: true };
};

const addRootScroll = (root: CollectionScrollRoot, delta: number): void => {
    if (!Number.isFinite(delta) || delta === 0) return;
    if (root instanceof HTMLElement) {
        root.scrollTop += delta;
        return;
    }
    root.scrollTo({ top: root.scrollY + delta });
};

const resetRootScroll = (root: CollectionScrollRoot): void => {
    if (root instanceof HTMLElement) {
        root.scrollTop = 0;
        return;
    }
    if (root.scrollY === 0) return;
    root.scrollTo({ top: 0 });
};

export { addRootScroll, measureCollectionBoundaries, readRootPosition, resetRootScroll, resolveCollectionScrollRoot };
export type { CollectionBoundaryMeasurement, CollectionScrollRoot };
