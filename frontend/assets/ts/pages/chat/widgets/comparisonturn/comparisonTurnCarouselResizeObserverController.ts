/* SoAI - Shared active-slide resize observation for comparison-turn carousels [frontend/assets/ts/pages/chat/widgets/comparisonturn/comparisonTurnCarouselResizeObserverController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ObservedCarouselSlide = {
    slide: HTMLElement;
    viewport: HTMLElement;
};

class ComparisonTurnCarouselResizeObserverController {
    readonly #observedByRoot = new Map<HTMLElement, ObservedCarouselSlide>();
    readonly #rootBySlide = new Map<HTMLElement, HTMLElement>();
    readonly #onResize: (root: HTMLElement, viewport: HTMLElement, slide: HTMLElement) => void;
    #observer: ResizeObserver | null = null;

    constructor(onResize: (root: HTMLElement, viewport: HTMLElement, slide: HTMLElement) => void) {
        this.#onResize = onResize;
    }

    sync(root: HTMLElement, viewport: HTMLElement, slide: HTMLElement): void {
        if (typeof ResizeObserver !== 'function') return;
        const previous = this.#observedByRoot.get(root) ?? null;
        if (previous?.slide === slide && previous.viewport === viewport) return;
        if (previous) this.#unobserve(root, previous.slide);
        const observer = this.#requireObserver();
        this.#observedByRoot.set(root, { slide, viewport });
        this.#rootBySlide.set(slide, root);
        observer.observe(slide);
    }

    pruneKnownRoots(knownRoots: ReadonlySet<HTMLElement>): void {
        for (const [root, observed] of this.#observedByRoot.entries()) {
            if (!root.isConnected || !knownRoots.has(root)) this.#unobserve(root, observed.slide);
        }
    }

    dispose(): void {
        this.#observer?.disconnect();
        this.#observer = null;
        this.#observedByRoot.clear();
        this.#rootBySlide.clear();
    }

    #requireObserver(): ResizeObserver {
        this.#observer ??= new ResizeObserver((entries) => {
            for (const entry of entries) {
                if (!(entry.target instanceof HTMLElement)) continue;
                const root = this.#rootBySlide.get(entry.target) ?? null;
                const observed = root ? (this.#observedByRoot.get(root) ?? null) : null;
                if (!root || !observed || observed.slide !== entry.target || !root.isConnected || !entry.target.isConnected || !root.contains(entry.target)) continue;
                this.#onResize(root, observed.viewport, entry.target);
            }
        });
        return this.#observer;
    }

    #unobserve(root: HTMLElement, slide: HTMLElement): void {
        this.#observer?.unobserve(slide);
        this.#observedByRoot.delete(root);
        if (this.#rootBySlide.get(slide) === root) this.#rootBySlide.delete(slide);
    }
}

export { ComparisonTurnCarouselResizeObserverController };
