/* SoAI - Model detail parameter category rail [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/parameterCategoryRailController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { inlineDelta, scrollByInline } from '@core/layout/direction.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { createLayoutFrameManager } from '@core/primitives/layoutFrameManager.ts';
import { PAGE_HEADER_STICKY_OFFSET_PROPERTY } from '@core/animations/constants.ts';
import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import type { ParameterGroup, ParameterView } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { isParameterGroup, isParameterView, PARAMETER_CATEGORY_SELECTOR, PARAMETER_VIEWS } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';
import type { ParameterViewHost } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';

type ParameterViewCounts = Record<ParameterView, number>;

const RAIL_SELECTOR = '.model-parameter-rail';
const PRESENCE_SUSPENDED_ATTRIBUTE = 'data-presence-suspended';
const RAIL_ITEM_SELECTOR = '.model-parameter-rail-item';
const RAIL_COUNT_SELECTOR = '.model-parameter-rail-count';
const SCROLL_CONTAINER_SELECTOR = '.page-scrollable';
const ACTIVE_CLASS = 'is-active';
const ACTIVE_LINE_RATIO = 0.25;
const NAVIGATION_LOCK_TIMEOUT_MS = 1000;

const toHTMLElements = (elements: Element[]): HTMLElement[] => elements.filter((element): element is HTMLElement => element instanceof HTMLElement);

class ParameterCategoryRailController {
    readonly #host: ParameterViewHost;
    readonly #frame = createLayoutFrameManager();
    #rail: HTMLElement | null = null;
    #scroller: HTMLElement | null = null;
    #sections: HTMLElement[] = [];
    #activeCategory: string | null = null;
    #navigationLocked = false;
    #navigationLockTimer: number | null = null;
    readonly #disposers: Array<() => void> = [];

    constructor(host: ParameterViewHost) {
        this.#host = host;
    }

    attach(container: Element): void {
        this.dispose();
        const rail = this.#host.pageDom.optionalHTMLElement(RAIL_SELECTOR, container);
        const scroller = container.closest(SCROLL_CONTAINER_SELECTOR);
        if (!rail || !(scroller instanceof HTMLElement)) {
            return;
        }
        this.#rail = rail;
        this.#scroller = scroller;
        this.#sections = toHTMLElements(this.#host.$$(PARAMETER_CATEGORY_SELECTOR, container));
        this.#disposers.push(this.#host.pageResources.on(scroller, 'scroll', this.#handleScroll, { passive: true }));
        this.#disposers.push(this.#host.pageResources.on(scroller, 'scrollend', this.#releaseNavigationLock, { passive: true }));
        this.#frame.queue(() => {
            this.#host.pageDom.updateAttribute(rail, PRESENCE_SUSPENDED_ATTRIBUTE, null);
            this.#syncActiveCategory();
        });
    }

    dispose(): void {
        this.#frame.cancel();
        this.#releaseNavigationLock();
        this.#disposers.splice(0).forEach((dispose) => dispose());
        this.#rail = null;
        this.#scroller = null;
        this.#sections = [];
        this.#activeCategory = null;
    }

    setView(view: ParameterView): void {
        this.#railItems().forEach((item) => {
            const itemView = item.dataset['parameterView'];
            if (!isParameterView(itemView)) {
                return;
            }
            this.#host.pageDom.toggleClass(item, ACTIVE_CLASS, itemView === view);
            this.#host.pageDom.updateAttribute(item, 'aria-pressed', String(itemView === view));
        });
    }

    setGroup(group: ParameterGroup | null): void {
        this.#railItems().forEach((item) => {
            const itemGroup = item.dataset['parameterGroup'];
            if (!isParameterGroup(itemGroup)) {
                return;
            }
            this.#host.pageDom.toggleClass(item, ACTIVE_CLASS, itemGroup === group);
            this.#host.pageDom.updateAttribute(item, 'aria-pressed', String(itemGroup === group));
        });
    }

    updateGroupCount(group: ParameterGroup, count: number): void {
        const item = this.#railItems().find((candidate) => candidate.dataset['parameterGroup'] === group);
        if (item) {
            this.#updateItemCount(item, count);
            this.#host.pageDom.toggleClass(item, CSS_CLASSES.HIDDEN, count === 0);
        }
    }

    updateViewCounts(counts: ParameterViewCounts): void {
        PARAMETER_VIEWS.forEach((view) => {
            const item = this.#railItems().find((candidate) => candidate.dataset['parameterView'] === view);
            if (item) {
                this.#updateItemCount(item, counts[view]);
            }
        });
    }

    updateCategoryCount(category: string, count: number): void {
        const item = this.#findCategoryItem(category);
        if (!item) {
            return;
        }
        this.#updateItemCount(item, count);
        this.#host.pageDom.toggleClass(item, CSS_CLASSES.HIDDEN, count === 0);
    }

    navigate(category: string): void {
        const section = this.#sections.find((candidate) => candidate.dataset['category'] === category);
        if (!section || section.classList.contains(CSS_CLASSES.HIDDEN)) {
            return;
        }
        const scroller = this.#scroller;
        if (!scroller) {
            return;
        }
        this.#lockNavigation();
        this.#setActiveCategory(category);
        const scrollMargin = Number.parseFloat(getComputedStyleStrict(section).scrollMarginTop) || 0;
        const scrollPadding = Number.parseFloat(getComputedStyleStrict(scroller).scrollPaddingTop) || 0;
        const targetTop = scroller.scrollTop + measureLayoutBox(section).top - measureLayoutBox(scroller).top - scrollMargin - scrollPadding;
        const maxScrollTop = scroller.scrollHeight - scroller.clientHeight;
        scroller.scrollTo({ top: Math.max(0, Math.min(targetTop, maxScrollTop)), behavior: prefersReducedMotion(scroller) ? 'auto' : 'smooth' });
    }

    scheduleSync(): void {
        this.#frame.queue(() => this.#syncActiveCategory());
    }

    readonly #handleScroll = (): void => {
        if (!this.#navigationLocked) {
            this.scheduleSync();
        }
    };

    readonly #releaseNavigationLock = (): void => {
        this.#navigationLocked = false;
        if (this.#navigationLockTimer !== null) {
            this.#host.pageResources.clearTimer(this.#navigationLockTimer);
            this.#navigationLockTimer = null;
        }
    };

    #lockNavigation(): void {
        this.#releaseNavigationLock();
        this.#navigationLocked = true;
        this.#navigationLockTimer = this.#host.pageResources.setTimeout(this.#releaseNavigationLock, NAVIGATION_LOCK_TIMEOUT_MS);
    }

    #railItems(): HTMLElement[] {
        return this.#rail ? toHTMLElements(this.#host.$$(RAIL_ITEM_SELECTOR, this.#rail)) : [];
    }

    #findCategoryItem(category: string): HTMLElement | null {
        return this.#railItems().find((item) => item.dataset['category'] === category) ?? null;
    }

    #updateItemCount(item: HTMLElement, count: number): void {
        const countElement = this.#host.pageDom.optional(RAIL_COUNT_SELECTOR, item);
        if (countElement) {
            this.#host.pageDom.updateText(countElement, i18n.formatNumber(count));
        }
    }

    #syncActiveCategory(): void {
        if (!this.#rail || this.#rail.getClientRects().length === 0) {
            return;
        }
        const scroller = this.#scroller;
        const visibleSections = this.#sections.filter((section) => section.isConnected && !section.classList.contains(CSS_CLASSES.HIDDEN));
        if (!scroller || !visibleSections.length) {
            this.#setActiveCategory(null);
            return;
        }
        const scrollerBox = measureLayoutBox(scroller);
        const headerOffset = Number.parseFloat(getComputedStyleStrict(scroller).getPropertyValue(PAGE_HEADER_STICKY_OFFSET_PROPERTY)) || 0;
        const activeLine = scrollerBox.top + headerOffset + (scroller.clientHeight - headerOffset) * ACTIVE_LINE_RATIO;
        const reachedEnd = scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 1;
        const active = reachedEnd ? visibleSections.at(-1) : (visibleSections.filter((section) => measureLayoutBox(section).top <= activeLine).at(-1) ?? visibleSections[0]);
        this.#setActiveCategory(active?.dataset['category'] ?? null);
    }

    #setActiveCategory(category: string | null): void {
        if (category === this.#activeCategory) {
            return;
        }
        this.#activeCategory = category;
        this.#railItems().forEach((item) => {
            const itemCategory = item.dataset['category'];
            if (itemCategory === undefined) {
                return;
            }
            const active = itemCategory === category;
            this.#host.pageDom.toggleClass(item, ACTIVE_CLASS, active);
            if (active) {
                this.#host.pageDom.updateAttribute(item, 'aria-current', 'location');
                this.#revealRailItem(item);
            } else {
                this.#host.pageDom.updateAttribute(item, 'aria-current', null);
            }
        });
    }

    #revealRailItem(item: HTMLElement): void {
        const rail = this.#rail;
        if (!rail || rail.scrollWidth <= rail.clientWidth) {
            return;
        }
        const railBox = measureLayoutBox(rail);
        const itemBox = measureLayoutBox(item);
        const overflowStart = itemBox.left - railBox.left;
        const overflowEnd = itemBox.right - railBox.right;
        const delta = overflowStart < 0 ? overflowStart : overflowEnd > 0 ? overflowEnd : 0;
        if (delta !== 0) {
            scrollByInline(rail, inlineDelta(delta, rail), prefersReducedMotion(rail) ? 'auto' : 'smooth');
        }
    }
}

export { ParameterCategoryRailController };
export type { ParameterViewCounts };
