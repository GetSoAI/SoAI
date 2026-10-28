/* SoAI - Shared UI auto scroller [frontend/assets/ts/core/ui/AutoScroller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { addRootScroll } from '@core/data/boundedcollectionrenderer/scrollRoot.ts';

interface ScrollConfig {
    edgeSize: number;
    speed: number;
}

const SCROLL_CONFIG: Readonly<ScrollConfig> = Object.freeze({
    edgeSize: 60,
    speed: 8
});

interface AutoScrollerOptions {
    scrollContainer: Element | Window | null;
}

class AutoScroller {
    private scrollContainer: HTMLElement | Window | null;

    constructor({ scrollContainer }: AutoScrollerOptions) {
        this.scrollContainer = scrollContainer instanceof HTMLElement || scrollContainer instanceof Window ? scrollContainer : null;
    }

    update(clientY: number, limits?: { upwardDistance: number; downwardDistance: number }): boolean {
        const container = this.scrollContainer;
        if (!container) {
            return false;
        }
        const bounds = container instanceof HTMLElement ? measureLayoutBox(container) : { top: 0, bottom: measureLayoutViewport(container.document).height };
        const topEdge = bounds.top + SCROLL_CONFIG.edgeSize;
        const bottomEdge = bounds.bottom - SCROLL_CONFIG.edgeSize;

        const upwardDistance = Math.max(0, Math.min(SCROLL_CONFIG.speed, limits?.upwardDistance ?? SCROLL_CONFIG.speed));
        const downwardDistance = Math.max(0, Math.min(SCROLL_CONFIG.speed, limits?.downwardDistance ?? SCROLL_CONFIG.speed));
        if (clientY < topEdge && upwardDistance > 0) {
            addRootScroll(container, -upwardDistance);
            return true;
        }
        if (clientY > bottomEdge && downwardDistance > 0) {
            addRootScroll(container, downwardDistance);
            return true;
        }
        return false;
    }

    setContainer(container: HTMLElement | null): void {
        this.scrollContainer = container;
    }

    destroy(): void {
        this.scrollContainer = null;
    }
}

export { AutoScroller, SCROLL_CONFIG };
export type { ScrollConfig, AutoScrollerOptions };
