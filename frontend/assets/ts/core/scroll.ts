/* SoAI - Shared scrolling primitives [frontend/assets/ts/core/scroll.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { dom, resolveAll } from '@core/dom/dom.ts';
import { getMatchMedia, getScrollTo, getWindow } from '@core/environment/public.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createHeaderActionController, type HeaderActionController } from '@core/headerActionBus.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import { onNavigationComplete, onNavigationStart } from '@core/navigationEvents.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isFunction } from '@core/typeGuards.ts';
import { throttle } from '@core/primitives/timing.ts';

if (!isFunction(ResourceTracker)) {
    throw new Error('ResourceTracker must load before scroll module');
}

interface ScrollIntoViewOptions {
    behavior?: ScrollBehavior;
    block?: ScrollLogicalPosition;
    inline?: ScrollLogicalPosition;
}

const createReducedMotionQuery = (): MediaQueryList => {
    const matchMedia = getMatchMedia();
    const query = matchMedia('(prefers-reduced-motion: reduce)');
    if (!query || typeof query.matches !== 'boolean') {
        throw new Error('matchMedia must return a MediaQueryList with matches property');
    }
    return query;
};

const scrollElementIntoView = (target: Element, options: ScrollIntoViewOptions = {}): void => {
    if (!target || !isFunction(target.scrollIntoView)) {
        throw new Error('scrollElementIntoView target must provide scrollIntoView');
    }
    const query = createReducedMotionQuery();
    const prefersReducedMotion = query.matches === true;
    const behavior = options.behavior ?? (prefersReducedMotion ? 'auto' : 'smooth');
    const block = options.block ?? 'nearest';
    target.scrollIntoView({ ...options, behavior, block });
};

const scrollElementToScrollerCenter = (scroller: HTMLElement, target: HTMLElement, options: { behavior?: ScrollBehavior } = {}): void => {
    const query = createReducedMotionQuery();
    const behavior = options.behavior ?? (query.matches === true ? 'auto' : 'smooth');
    const scrollerRect = measureLayoutBox(scroller);
    const targetRect = measureLayoutBox(target);
    const targetOffsetWithinScroller = scroller.scrollTop + (targetRect.top - scrollerRect.top);
    const centeredTop = targetOffsetWithinScroller - (scroller.clientHeight - targetRect.height) / 2;
    const maxScrollTop = scroller.scrollHeight - scroller.clientHeight;
    scroller.scrollTo({ top: Math.max(0, Math.min(centeredTop, maxScrollTop)), behavior });
};

class ScrollToTop {
    threshold: number;
    isVisible: boolean;
    isMobile: boolean;
    scrollHandler: (() => void) | null;
    scrollableElements: Set<HTMLElement>;
    resources: ResourceTracker;
    actionContextId: string;
    handleActionInvoke: () => void;
    actionController: HeaderActionController;
    navigationUnsubscribe: (() => void) | null;
    mediaQueryListenerAttached: boolean;
    modalListenersAttached: boolean;

    constructor() {
        this.threshold = 300;
        this.isVisible = false;
        this.isMobile = false;
        this.scrollHandler = null;
        this.scrollableElements = new Set();
        this.resources = new ResourceTracker();
        this.actionContextId = HEADER_ACTION_IDS.scrollToTop;
        this.handleActionInvoke = () => {
            this.scrollToTop();
        };
        this.actionController = createHeaderActionController({
            actionId: HEADER_ACTION_IDS.scrollToTop,
            contextId: this.actionContextId
        });
        this.navigationUnsubscribe = null;
        this.mediaQueryListenerAttached = false;
        this.modalListenersAttached = false;
    }

    initialize(): void {
        this.actionController.update({
            visible: false,
            onClick: this.handleActionInvoke
        });

        this.checkMobileState();
        this.setupMediaQuery();
        this.setupModalListeners();
        this.setupNavigationListener();

        if (this.isMobile) return;

        this.attachScrollListeners();
        this.checkScrollPosition();
    }

    setupNavigationListener(): void {
        if (this.navigationUnsubscribe) {
            return;
        }
        const startUnsubscribe = onNavigationStart(() => {
            this.hideButton();
        });
        const completeUnsubscribe = onNavigationComplete(() => {
            this.hideButton();
            if (!this.isMobile) {
                this.resources.requestAnimationFrame(() => {
                    this.registerScrollableElements();
                    this.checkScrollPosition();
                });
            }
        });
        this.navigationUnsubscribe = () => {
            startUnsubscribe();
            completeUnsubscribe();
        };
    }

    setupModalListeners(): void {
        if (this.modalListenersAttached) {
            return;
        }
        this.modalListenersAttached = true;
        const documentRef = dom.getDocument();
        this.resources.addEventListener(documentRef, 'core.modal.open', () => {
            this.hideButton();
        });
        this.resources.addEventListener(documentRef, 'core.modal.close', () => {
            if (!this.isMobile) {
                this.resources.requestAnimationFrame(() => this.checkScrollPosition());
            }
        });
    }

    attachScrollListeners(): void {
        if (this.scrollHandler) {
            return;
        }
        this.scrollHandler = throttle(() => this.checkScrollPosition(), 100);
        const windowRef = getWindow();
        this.resources.addEventListener(windowRef, 'scroll', this.scrollHandler, { passive: true });
        this.registerScrollableElements();
    }

    cleanupDetachedElements(): void {
        if (!this.scrollableElements.size) {
            return;
        }
        Array.from(this.scrollableElements)
            .filter((element) => !element.isConnected)
            .forEach((element) => {
                if (this.scrollHandler) {
                    this.resources.removeEventListener(element, 'scroll', this.scrollHandler, { passive: true });
                }
                this.scrollableElements.delete(element);
            });
    }

    registerScrollableElements(): void {
        const scrollHandler = this.scrollHandler;
        if (!scrollHandler) {
            return;
        }

        this.cleanupDetachedElements();

        const documentRef = dom.getDocument();
        resolveAll('.page-scrollable', documentRef).forEach((element: Element) => {
            if (!(element instanceof HTMLElement)) {
                errorHandler.warn('Scroll', 'Expected .page-scrollable to resolve to an HTMLElement', element);
                return;
            }
            if (this.scrollableElements.has(element)) {
                return;
            }
            this.resources.addEventListener(element, 'scroll', scrollHandler, { passive: true });
            this.scrollableElements.add(element);
        });
    }

    getTrackedScrollableElements(): HTMLElement[] {
        this.cleanupDetachedElements();
        return Array.from(this.scrollableElements);
    }

    checkMobileState(): void {
        this.isMobile = measureLayoutViewport().width <= 319;
    }

    setupMediaQuery(): void {
        if (this.mediaQueryListenerAttached) {
            return;
        }
        this.mediaQueryListenerAttached = true;
        const synchronize = (): void => {
            this.checkMobileState();
            if (this.isMobile) {
                this.hideButton();
            } else {
                this.attachScrollListeners();
                this.checkScrollPosition();
            }
        };
        const windowRef = getWindow();
        this.resources.addEventListener(windowRef, 'resize', synchronize);
        this.resources.addEventListener(windowRef, INTERFACE_SCALE_CHANGED_EVENT, synchronize);
    }

    checkScrollPosition(): void {
        if (this.isScrollTopActionSuppressed()) {
            if (this.isVisible) {
                this.hideButton();
            }
            return;
        }
        const scrollTop = this.getCurrentScrollTop();
        const shouldShow = scrollTop > this.threshold;

        if (shouldShow && !this.isVisible) {
            this.showButton();
        } else if (!shouldShow && this.isVisible) {
            this.hideButton();
        }
    }

    getCurrentScrollTop(): number {
        const windowRef = getWindow();
        const { scrollY } = windowRef;
        const root = dom.getDocument().scrollingElement;
        const windowScroll = Number.isFinite(scrollY) ? Math.max(0, scrollY) : Math.max(0, root?.scrollTop ?? 0);

        const tracked = this.getTrackedScrollableElements();
        if (!tracked.length) {
            return windowScroll;
        }
        const maxElementScroll = Math.max(0, ...tracked.map((element) => element.scrollTop));
        return Math.max(windowScroll, maxElementScroll);
    }

    isScrollTopActionSuppressed(): boolean {
        const documentRef = dom.getDocument();
        if (documentRef.body?.dataset['scrollTopAction'] === 'disabled') {
            return true;
        }
        if (documentRef.body?.classList.contains('scroll-top-action-disabled')) {
            return true;
        }
        return resolveAll('.ui-modal:not(.u-hidden)', documentRef).some((element) => element instanceof HTMLElement && element.isConnected);
    }

    private scrollToTop(): void {
        const scrollTo = getScrollTo();
        scrollTo({ top: 0, behavior: 'smooth' });

        this.getTrackedScrollableElements().forEach((element) => {
            if (element.scrollTop > 0) {
                element.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
    }

    showButton(): void {
        if (this.isScrollTopActionSuppressed()) {
            return;
        }
        this.isVisible = true;
        this.actionController.show({
            onClick: this.handleActionInvoke
        });
    }

    hideButton(): void {
        this.isVisible = false;
        this.actionController.update({
            visible: false,
            onClick: this.handleActionInvoke
        });
    }
}

let scrollModuleInstance: ScrollToTop | null = null;

const getScrollModule = (): ScrollToTop => {
    if (!scrollModuleInstance) {
        scrollModuleInstance = new ScrollToTop();
    }
    return scrollModuleInstance;
};

export { ScrollToTop, getScrollModule, scrollElementIntoView, scrollElementToScrollerCenter };
