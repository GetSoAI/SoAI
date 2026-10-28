/* SoAI - Shared animations state [frontend/assets/ts/core/animations/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { HeaderScrollInput, type HeaderScrollInputDirection } from '@core/animations/headerScrollInput.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { dispatchCustomEvent, getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { HYSTERESIS_BUFFER, PAGE_HEADER_STATE_CHANGED_EVENT, PAGE_HEADER_STICKY_OFFSET_PROPERTY, SCROLL_THRESHOLD } from '@core/animations/constants.ts';
import { type HeaderState } from '@core/animations/types.ts';

class HeaderAnimator {
    container: HTMLElement | null;
    observer: ResizeObserver | null;
    header: HTMLElement | null;
    headerHeight: number;
    lastScroll: number;
    state: HeaderState;
    rafId: number | null;
    autoHideEnabled: boolean;
    resources: ResourceTracker;
    handleScroll: () => void;
    #handleScrollImpl: () => void;
    #stickyOffset: number | null = null;
    #scrollInput: HeaderScrollInput | null = null;
    #scrollDirection: HeaderScrollInputDirection = null;
    #transitionResetRafId: number | null = null;

    constructor(scrollContainer: HTMLElement, resizeObserver: ResizeObserver | null, autoHideEnabled: boolean = true) {
        this.container = scrollContainer;
        this.observer = resizeObserver;
        this.header = null;
        this.headerHeight = 0;
        this.lastScroll = 0;
        this.state = 'EXTENDED';
        this.rafId = null;
        this.autoHideEnabled = autoHideEnabled !== false;
        this.resources = new ResourceTracker();

        this.#handleScrollImpl = (): void => {
            this.#scrollDirection = this.container ? (this.#scrollInput?.captureDirection(this.container.scrollTop - this.lastScroll) ?? null) : null;
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
                    this.#syncStickyOffset();
                    this.#emitStateChanged(false);
                    this.rafId = null;
                    return;
                }

                const delta = scrollTop - this.lastScroll;

                if (this.#scrollDirection === null || (this.#scrollDirection === 'up' && delta >= 0) || (this.#scrollDirection === 'down' && delta <= 0)) {
                    this.lastScroll = scrollTop;
                    this.rafId = null;
                    return;
                }

                if (delta !== 0 && scrollTop <= this.headerHeight) {
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

        this.#scrollInput = new HeaderScrollInput(this.container, this.resources, () => this.reveal());
        this.updateHeaderHeight();
        this.resources.addEventListener(this.container, 'scroll', this.handleScroll, { passive: true });
        this.resources.addEventListener(this.header, 'focusin', () => this.reveal());
        this.observer?.observe(this.header, { box: 'border-box' });

        if (this.autoHideEnabled) {
            this.applyState('EXTENDED', true);
        } else {
            this.#removeStateClasses();
            this.state = null;
            this.#syncStickyOffset();
        }
        this.lastScroll = this.container.scrollTop || 0;
        return true;
    }

    updateHeaderHeight(): void {
        if (!this.header || !this.container) return;
        const rect = measureLayoutBox(this.header);

        this.headerHeight = rect.height;
        this.#syncStickyOffset();
    }

    setAutoHideEnabled(enabled: boolean): void {
        const next = enabled !== false;
        if (this.autoHideEnabled === next) return;
        this.autoHideEnabled = next;
        this.#scrollInput?.clearScrollDirection();
        this.#scrollDirection = null;

        if (!next) {
            this.lastScroll = this.container?.scrollTop || 0;
            this.#removeStateClasses();
            this.state = null;
            this.#syncStickyOffset();
            this.#emitStateChanged(false);
            return;
        }

        if (this.state === null) {
            this.applyState('EXTENDED', true);
        }
    }

    reveal(): void {
        this.#scrollInput?.clearScrollDirection();
        this.#scrollDirection = null;
        if (this.autoHideEnabled) this.applyState('EXTENDED');
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

        if (this.#transitionResetRafId !== null) {
            this.resources.cancelAnimationFrame(this.#transitionResetRafId);
            this.#transitionResetRafId = null;
        }
        classList.toggle('page-header-panel--no-transition', noTransition);

        classList.remove('page-header-panel--extended', 'page-header-panel--folded');
        classList.add(`page-header-panel--${newState.toLowerCase()}`);
        this.state = newState;
        this.#syncStickyOffset();
        this.#emitStateChanged(newState === 'FOLDED');

        if (!noTransition) return;

        this.#transitionResetRafId = this.resources.requestAnimationFrame(() => {
            this.#transitionResetRafId = this.resources.requestAnimationFrame(() => {
                this.#transitionResetRafId = null;
                classList.remove('page-header-panel--no-transition');
            });
        });
    }

    #syncStickyOffset(): void {
        if (!this.container || !this.header) return;
        const headerCoversContent = this.header.classList.contains('is-floating') && this.state !== 'FOLDED';
        const stickyOffset = headerCoversContent ? this.headerHeight : 0;
        if (stickyOffset === this.#stickyOffset) return;
        this.#stickyOffset = stickyOffset;
        dom.setStyle(this.container, PAGE_HEADER_STICKY_OFFSET_PROPERTY, `${stickyOffset}px`);
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

        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }

        this.resources.cleanup();
        this.#scrollInput = null;
        this.#transitionResetRafId = null;
        if (this.header) {
            this.observer?.unobserve(this.header);
        }
        if (this.header) {
            this.header.classList.add('page-header-panel--no-transition');
            this.header.classList.remove('page-header-panel--extended', 'page-header-panel--folded');
            dom.setStyle(this.header, 'transform', null);
        }
        if (this.container) {
            dom.setStyle(this.container, PAGE_HEADER_STICKY_OFFSET_PROPERTY, null);
        }
        this.#stickyOffset = null;

        this.container = null;
        this.header = null;
    }
}

export { HeaderAnimator };
