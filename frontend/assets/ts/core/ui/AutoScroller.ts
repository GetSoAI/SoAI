/* SoAI - Shared UI auto scroller [frontend/assets/ts/core/ui/AutoScroller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';

interface ScrollConfig {
    edgeSize: number;
    speed: number;
}

const SCROLL_CONFIG: Readonly<ScrollConfig> = Object.freeze({
    edgeSize: 60,
    speed: 8
});

interface AutoScrollerOptions {
    scrollContainer: Element | null;
}

class AutoScroller {
    private scrollContainer: HTMLElement | null;

    constructor({ scrollContainer }: AutoScrollerOptions) {
        this.scrollContainer = scrollContainer instanceof HTMLElement ? scrollContainer : null;
    }

    update(clientY: number): boolean {
        const container = this.scrollContainer;
        if (!container) {
            return false;
        }
        const rect = measureLayoutBox(container);
        const topEdge = rect.top + SCROLL_CONFIG.edgeSize;
        const bottomEdge = rect.bottom - SCROLL_CONFIG.edgeSize;

        if (clientY < topEdge) {
            container.scrollTop -= SCROLL_CONFIG.speed;
            return true;
        }
        if (clientY > bottomEdge) {
            container.scrollTop += SCROLL_CONFIG.speed;
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
