/* SoAI - Caches per-slide viewport heights for comparison-turn carousels [frontend/assets/ts/pages/chat/widgets/comparisonturn/comparisonTurnCarouselViewportHeightCacheController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class ComparisonTurnCarouselViewportHeightCache {
    readonly #heightByRootAndSlideIndex = new Map<HTMLElement, Map<number, number>>();
    readonly #appliedHeightByRoot = new Map<HTMLElement, number>();

    dispose(): void {
        this.#heightByRootAndSlideIndex.clear();
        this.#appliedHeightByRoot.clear();
    }

    pruneKnownRoots(knownRoots: ReadonlySet<HTMLElement>): void {
        for (const root of Array.from(this.#heightByRootAndSlideIndex.keys())) {
            if (!root.isConnected || !knownRoots.has(root)) {
                this.#heightByRootAndSlideIndex.delete(root);
            }
        }
        for (const root of Array.from(this.#appliedHeightByRoot.keys())) {
            if (!root.isConnected || !knownRoots.has(root)) {
                this.#appliedHeightByRoot.delete(root);
            }
        }
    }

    read(root: HTMLElement, slideIndex: number): number {
        const byIndex = this.#heightByRootAndSlideIndex.get(root) ?? null;
        if (!byIndex) {
            return 0;
        }
        return byIndex.get(slideIndex) ?? 0;
    }

    write(root: HTMLElement, slideIndex: number, height: number): void {
        let byIndex = this.#heightByRootAndSlideIndex.get(root) ?? null;
        if (!byIndex) {
            byIndex = new Map<number, number>();
            this.#heightByRootAndSlideIndex.set(root, byIndex);
        }
        byIndex.set(slideIndex, height);
    }

    readApplied(root: HTMLElement): number {
        return this.#appliedHeightByRoot.get(root) ?? 0;
    }

    writeApplied(root: HTMLElement, height: number): void {
        this.#appliedHeightByRoot.set(root, height);
    }
}

export { ComparisonTurnCarouselViewportHeightCache };
