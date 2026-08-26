/* SoAI - Shared animations state [frontend/assets/ts/core/animations/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { dispatchCustomEvent, getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { HYSTERESIS_BUFFER, MARGIN_SAFETY, PAGE_HEADER_STATE_CHANGED_EVENT, SCROLL_THRESHOLD } from '@core/animations/constants.ts';
import { type HeaderState } from '@core/animations/types.ts';

class HeaderAnimator {
    container: HTMLElement | null;
    observer: ResizeObserver | null;
    header: HTMLElement | null;
    headerResizeRafId: number | null;
    headerHeight: number;
    lastScroll: number;
    state: HeaderState;
    rafId: number | null;
    autoHideEnabled: boolean;
    resources: ResourceTracker;
    handleScroll: () => void;
    #handleScrollImpl: () => void;

    constructor(scrollContainer: HTMLElement, resizeObserver: ResizeObserver | null, autoHideEnabled: boolean = true) {
        this.container = scrollContainer;
        this.observer = resizeObserver;
        this.header = null;
        this.headerResizeRafId = null;
        this.headerHeight = 0;
        this.lastScroll = 0;
        this.state = 'EXTENDED';
        this.rafId = null;
        this.autoHideEnabled = autoHideEnabled !== false;
        this.resources = new ResourceTracker();

        this.#handleScrollImpl = (): void => {
            if (this.rafId) return;

            const requestAnimationFrame = getRequestAnimationFrame();
            this.rafId = requestAnimationFrame(() => {
                if (!this.container) {
                    this.rafId = null;
                    return;
                }
                const scrollTop = this.container.scrollTop;

                if (!this.autoHideEnabled) {
                    this.lastScroll = scrollTop;
                    this.#removeStateClasses();
                    this.state = null;
                    this.#emitStateChanged(false);
                    this.rafId = null;
                    return;
                }

                const delta = scrollTop - this.lastScroll;

                if (scrollTop <= this.headerHeight) {
                    if (this.state !== 'EXTENDED') this.applyState('EXTENDED');
                } else if (delta > SCROLL_THRESHOLD && scrollTop > this.headerHeight + HYSTERESIS_BUFFER) {
                    if (this.state !== 'FOLDED') this.applyState('FOLDED');
                } else if (delta < -SCROLL_THRESHOLD && this.state === 'FOLDED') {
                    this.applyState('EXTENDED');
                }

                this.lastScroll = scrollTop;
                this.rafId = null;
            });
        };
        this.handleScroll = this.#handleScrollImpl;
    }

    initialize(): boolean {
        if (!this.container) return false;
        const headerCandidate = dom.resolve('.page-header-panel', this.container);
        this.header = headerCandidate instanceof HTMLElement ? headerCandidate : null;
        if (!this.header) return false;

        this.updateHeaderHeight();
        this.resources.addEventListener(this.container, 'scroll', this.handleScroll, { passive: true });
        this.observer?.observe(this.header);

        if (this.autoHideEnabled) {
            this.applyState('EXTENDED', true);
        } else {
            this.#removeStateClasses();
            this.state = null;
        }
        this.lastScroll = this.container.scrollTop || 0;
        return true;
    }

    queueHeaderHeightUpdate(): void {
        if (this.headerResizeRafId) return;

        const requestAnimationFrame = getRequestAnimationFrame();
        this.headerResizeRafId = requestAnimationFrame(() => {
            this.headerResizeRafId = null;
            if (!this.header || !this.container) return;
            this.updateHeaderHeight();
        });
    }

    updateHeaderHeight(): void {
        if (!this.header || !this.container) return;
        const rect = measureLayoutBox(this.header);
        const marginBottom = parseFloat(getComputedStyle(this.header).marginBottom) || 0;

        this.headerHeight = rect.height;
        dom.setStyle(this.header, '--header-measured-height', `${rect.height + marginBottom + MARGIN_SAFETY}px`);

        if (this.container.scrollTop < this.headerHeight) {
            this.applyState('EXTENDED', true);
        }
    }

    setAutoHideEnabled(enabled: boolean): void {
        const next = enabled !== false;
        if (this.autoHideEnabled === next) return;
        this.autoHideEnabled = next;

        if (!next) {
            this.lastScroll = this.container?.scrollTop || 0;
            this.#removeStateClasses();
            this.state = null;
            this.#emitStateChanged(false);
            return;
        }

        if (this.state === null) {
            this.applyState('EXTENDED', true);
        }
    }

    setScrollTopWithoutReaction(scrollTop: number): void {
        if (!Number.isFinite(scrollTop)) {
            throw new TypeError('Header scroll position must be finite');
        }
        if (!this.container) return;
        this.container.scrollTop = Math.max(0, scrollTop);
        this.lastScroll = this.container.scrollTop;
    }

    private applyState(newState: 'EXTENDED' | 'FOLDED', noTransition: boolean = false): void {
        if (this.state === newState && !noTransition) return;
        if (!this.header) return;

        const classList = this.header.classList;

        if (noTransition) {
            classList.add('page-header-panel--no-transition');
        }

        classList.remove('page-header-panel--extended', 'page-header-panel--folded');
        classList.add(`page-header-panel--${newState.toLowerCase()}`);
        this.state = newState;
        this.#emitStateChanged(newState === 'FOLDED');

        if (!noTransition) return;

        const requestAnimationFrame = getRequestAnimationFrame();
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                classList.remove('page-header-panel--no-transition');
            });
        });
    }

    #removeStateClasses(): void {
        if (!this.header?.classList) return;
        this.header.classList.remove('page-header-panel--extended', 'page-header-panel--folded', 'page-header-panel--no-transition');
    }

    #emitStateChanged(collapsed: boolean): void {
        dispatchCustomEvent(PAGE_HEADER_STATE_CHANGED_EVENT, { collapsed });
    }

    destroy(): void {
        const cancelAnimationFrame = getCancelAnimationFrame();

        if (this.headerResizeRafId) {
            cancelAnimationFrame(this.headerResizeRafId);
            this.headerResizeRafId = null;
        }
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }

        this.resources?.cleanup();
        if (this.header) {
            this.observer?.unobserve(this.header);
        }
        if (this.header) {
            this.header.classList.add('page-header-panel--no-transition');
            this.header.classList.remove('page-header-panel--extended', 'page-header-panel--folded');
            dom.setStyle(this.header, '--header-measured-height', null);
            dom.setStyle(this.header, 'transform', null);
        }

        this.container = null;
        this.header = null;
    }
}

export { HeaderAnimator };
