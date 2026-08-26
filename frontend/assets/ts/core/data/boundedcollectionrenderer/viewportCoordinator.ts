/* SoAI - Bounded collection viewport observation and edge intent [frontend/assets/ts/core/data/boundedcollectionrenderer/viewportCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { measureCollectionBoundaries, readRootPosition, resetRootScroll, resolveCollectionScrollRoot, type CollectionScrollRoot } from '@core/data/boundedcollectionrenderer/scrollRoot.ts';
import type { CollectionEdge, CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/types.ts';
import { resolveScrollDirection } from '@core/dom/scrollGeometry.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

const EXPLICIT_ANCHOR_CLASS = 'ui-collection-explicit-anchor';

interface CollectionViewportCallbacks {
    onEdge: (edge: CollectionEdge) => void;
    onUnderfill: () => void;
    onContainerReady: () => void;
}

const resolveCollectionElement = (children: HTMLCollection, index: number): HTMLElement | null => {
    const element = children.item(index);
    return element instanceof HTMLElement && element.dataset['collectionId'] !== undefined ? element : null;
};

const resolveFirstVisibleElement = (container: HTMLElement, viewportTop: number): HTMLElement | null => {
    const children = container.children;
    let lowerIndex = 0;
    let upperIndex = children.length - 1;
    while (lowerIndex <= upperIndex && resolveCollectionElement(children, lowerIndex) === null) lowerIndex += 1;
    while (upperIndex >= lowerIndex && resolveCollectionElement(children, upperIndex) === null) upperIndex -= 1;
    let visible: HTMLElement | null = null;
    while (lowerIndex <= upperIndex) {
        const middleIndex = Math.floor((lowerIndex + upperIndex) / 2);
        const element = resolveCollectionElement(children, middleIndex);
        if (element === null) return null;
        if (measureLayoutBox(element).bottom > viewportTop) {
            visible = element;
            upperIndex = middleIndex - 1;
        } else {
            lowerIndex = middleIndex + 1;
        }
    }
    return visible;
};

class CollectionViewportCoordinator {
    readonly #callbacks: CollectionViewportCallbacks;
    readonly #resources = new ResourceTracker();
    #container: HTMLElement | null = null;
    #scrollRoot: CollectionScrollRoot | null = null;
    #removeScrollListener: (() => void) | null = null;
    #resizeObserver: ResizeObserver | null = null;
    #scrollFrame: number | null = null;
    #underfillFrame: number | null = null;
    #lastScrollPosition = 0;
    #forwardArmed = true;
    #backwardArmed = true;
    #disposed = false;

    constructor(callbacks: CollectionViewportCallbacks) {
        this.#callbacks = callbacks;
    }

    get container(): HTMLElement | null {
        return this.#container;
    }

    attach(container: HTMLElement): HTMLElement | null {
        if (this.#disposed) throw new Error('Disposed collection viewport cannot attach a container');
        if (this.#container === container) {
            this.#refreshScrollRoot();
            return null;
        }
        const previous = this.#container;
        this.#detach();
        this.#container = container;
        container.classList.add(EXPLICIT_ANCHOR_CLASS);
        this.#resizeObserver = new ResizeObserver(() => {
            this.#refreshScrollRoot();
            if (container.isConnected) this.#callbacks.onContainerReady();
            this.scheduleUnderfillCheck();
        });
        this.#resizeObserver.observe(container);
        this.#resources.track(this.#resizeObserver, (observer) => observer.disconnect());
        this.#refreshScrollRoot();
        this.#forwardArmed = true;
        this.#backwardArmed = true;
        return previous;
    }

    resetScroll(): void {
        this.#refreshScrollRoot();
        if (this.#scrollRoot !== null) resetRootScroll(this.#scrollRoot);
    }

    resolveFirstVisibleAnchor(): CollectionViewportAnchor | null {
        if (this.#container === null || this.#scrollRoot === null) return null;
        const viewportTop = this.#scrollRoot instanceof HTMLElement ? measureLayoutBox(this.#scrollRoot).top : 0;
        const atStart = readRootPosition(this.#scrollRoot) === 0;
        const element = resolveFirstVisibleElement(this.#container, viewportTop);
        const identifier = element?.dataset['collectionId'];
        if (element === null || identifier === undefined) return null;
        return { identifier, offset: measureLayoutBox(element).top - viewportTop, atStart };
    }

    isAtEnd(): boolean {
        if (this.#container === null || this.#scrollRoot === null) return false;
        const measurement = measureCollectionBoundaries(this.#container, this.#scrollRoot);
        return measurement.measurable && measurement.atEnd;
    }

    isAtEdge(edge: CollectionEdge): boolean {
        if (this.#container === null || this.#scrollRoot === null) return false;
        const measurement = measureCollectionBoundaries(this.#container, this.#scrollRoot);
        return measurement.measurable && (edge === 'forward' ? measurement.atEnd : measurement.atStart);
    }

    committed(): void {
        this.#refreshScrollRoot();
        if (this.#container === null || this.#scrollRoot === null) return;
        this.#lastScrollPosition = readRootPosition(this.#scrollRoot);
        const measurement = measureCollectionBoundaries(this.#container, this.#scrollRoot);
        if (measurement.measurable && !measurement.atEnd) this.#forwardArmed = true;
        if (measurement.measurable && !measurement.atStart) this.#backwardArmed = true;
        this.scheduleUnderfillCheck();
    }

    scheduleUnderfillCheck(): void {
        if (this.#disposed || this.#underfillFrame !== null) return;
        this.#underfillFrame = this.#resources.requestAnimationFrame(() => {
            this.#underfillFrame = null;
            if (this.#disposed) return;
            this.#refreshScrollRoot();
            if (this.#container === null || this.#scrollRoot === null) return;
            const measurement = measureCollectionBoundaries(this.#container, this.#scrollRoot);
            if (measurement.measurable && measurement.atStart && measurement.atEnd) this.#callbacks.onUnderfill();
        });
    }

    suspendSurface(): void {
        if (this.#disposed) return;
        this.#detach();
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#detach();
        this.#resources.cleanup();
    }

    #scheduleScrollCheck(): void {
        if (this.#disposed || this.#scrollFrame !== null) return;
        this.#scrollFrame = this.#resources.requestAnimationFrame(() => {
            this.#scrollFrame = null;
            if (this.#disposed) return;
            if (this.#container === null || this.#scrollRoot === null) return;
            const measurement = measureCollectionBoundaries(this.#container, this.#scrollRoot);
            const direction = resolveScrollDirection(this.#lastScrollPosition, measurement.position);
            this.#lastScrollPosition = measurement.position;
            if (!measurement.atEnd) this.#forwardArmed = true;
            if (!measurement.atStart) this.#backwardArmed = true;
            if (direction === 'forward' && measurement.atEnd && this.#forwardArmed) {
                this.#forwardArmed = false;
                this.#callbacks.onEdge('forward');
            } else if (direction === 'backward' && measurement.atStart && this.#backwardArmed) {
                this.#backwardArmed = false;
                this.#callbacks.onEdge('backward');
            }
        });
    }

    #refreshScrollRoot(): void {
        const nextRoot = this.#container?.isConnected === true ? resolveCollectionScrollRoot(this.#container) : null;
        if (this.#scrollRoot === nextRoot) return;
        this.#removeScrollListener?.();
        this.#removeScrollListener = null;
        this.#scrollRoot = nextRoot;
        if (nextRoot === null) return;
        this.#lastScrollPosition = readRootPosition(nextRoot);
        this.#removeScrollListener = this.#resources.addEventListener(nextRoot, 'scroll', () => this.#scheduleScrollCheck(), { passive: true });
    }

    #detach(): void {
        this.#container?.classList.remove(EXPLICIT_ANCHOR_CLASS);
        this.#removeScrollListener?.();
        this.#removeScrollListener = null;
        if (this.#scrollFrame !== null) {
            this.#resources.cancelAnimationFrame(this.#scrollFrame);
            this.#scrollFrame = null;
        }
        if (this.#underfillFrame !== null) {
            this.#resources.cancelAnimationFrame(this.#underfillFrame);
            this.#underfillFrame = null;
        }
        if (this.#resizeObserver !== null) {
            this.#resizeObserver.disconnect();
            this.#resources.untrack(this.#resizeObserver);
        }
        this.#resizeObserver = null;
        this.#container = null;
        this.#scrollRoot = null;
    }
}

export { CollectionViewportCoordinator };
