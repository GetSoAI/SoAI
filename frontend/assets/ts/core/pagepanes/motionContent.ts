/* SoAI - Layout item glide for panes whose content reflows during pane motion [frontend/assets/ts/core/pagepanes/motionContent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';

interface PagePaneItemBox {
    readonly x: number;
    readonly y: number;
    readonly width: number;
    readonly height: number;
}

type PagePaneItemPositions = ReadonlyMap<HTMLElement, PagePaneItemBox>;

const PAGE_PANE_SECTION_SELECTOR = ':scope > .page-pane-outlet > [data-section]';

const resolvePagePaneSection = (root: HTMLElement): HTMLElement | null => {
    const section = dom.resolve(PAGE_PANE_SECTION_SELECTOR, root);
    return section instanceof HTMLElement ? section : null;
};
const PAGE_PANE_ITEM_DEPTH = 6;
const PAGE_PANE_ITEM_LIMIT = 240;
const PAGE_PANE_ITEM_TOLERANCE_PX = 0.5;

const isPagePaneItemContainer = (display: string): boolean => display === 'grid' || display === 'inline-grid';

const isPagePaneItemDisplayed = (element: Element): element is HTMLElement => element instanceof HTMLElement && getComputedStyleStrict(element).display !== 'none';

const PAGE_PANE_ITEM_TRANSPARENT = 'rgba(0, 0, 0, 0)';

const isPagePaneItemSurface = (style: CSSStyleDeclaration): boolean => style.backgroundColor !== PAGE_PANE_ITEM_TRANSPARENT || style.backgroundImage !== 'none' || style.boxShadow !== 'none' || style.backdropFilter !== 'none' || ['Top', 'Right', 'Bottom', 'Left'].some((side) => Number.parseFloat(style.getPropertyValue(`border-${side.toLowerCase()}-width`)) > 0);

const collectPagePaneItemLevel = (elements: Iterable<Element>, depth: number, items: HTMLElement[]): boolean => {
    const leaves: HTMLElement[] = [];
    let found = false;
    for (const child of elements) {
        if (collectPagePaneItems(child, depth, items)) found = true;
        else if (isPagePaneItemDisplayed(child)) leaves.push(child);
    }
    if (found) items.push(...leaves.slice(0, Math.max(0, PAGE_PANE_ITEM_LIMIT - items.length)));
    return found;
};

const collectPagePaneItems = (element: Element, depth: number, items: HTMLElement[]): boolean => {
    if (items.length >= PAGE_PANE_ITEM_LIMIT || !(element instanceof HTMLElement)) return false;
    const style = getComputedStyleStrict(element);
    const display = style.display;
    if (display === 'none' || display === 'contents' || isPagePaneItemSurface(style)) return false;
    if (isPagePaneItemContainer(display)) {
        for (const child of element.children) {
            if (items.length < PAGE_PANE_ITEM_LIMIT && isPagePaneItemDisplayed(child)) items.push(child);
        }
        return element.children.length > 0;
    }
    return depth < PAGE_PANE_ITEM_DEPTH && collectPagePaneItemLevel(element.children, depth + 1, items);
};

const measurePagePaneItemOrigin = (section: Element): { readonly left: number; readonly top: number } => {
    const box = measureLayoutBox(section);
    const style = getComputedStyleStrict(section);
    return { left: style.direction === 'rtl' ? box.right : box.left, top: box.top + Number.parseFloat(style.borderTopWidth) + Number.parseFloat(style.paddingTop) };
};

const measurePagePaneItems = (root: HTMLElement, items: Iterable<HTMLElement> | null = null): Map<HTMLElement, PagePaneItemBox> => {
    const positions = new Map<HTMLElement, PagePaneItemBox>();
    const section = resolvePagePaneSection(root);
    if (section === null) return positions;
    const origin = measurePagePaneItemOrigin(section);
    let candidates: Iterable<HTMLElement> | null = items;
    if (candidates === null) {
        const collected: HTMLElement[] = [];
        if (!collectPagePaneItemLevel(section.children, 1, collected)) collected.push(...Array.from(section.children).filter(isPagePaneItemDisplayed));
        candidates = collected;
    }
    for (const item of candidates) {
        if (!item.isConnected) continue;
        const box = measureLayoutBox(item);
        if (box.width > 0 && box.height > 0) positions.set(item, { x: box.left - origin.left, y: box.top - origin.top, width: box.width, height: box.height });
    }
    return positions;
};

const PAGE_PANE_FADE_IN_END = 0.45;
const PAGE_PANE_RESIZE_TOLERANCE_PX = 1;

const isPagePaneItemResized = (start: PagePaneItemBox, end: PagePaneItemBox): boolean => Math.abs(start.width - end.width) > PAGE_PANE_RESIZE_TOLERANCE_PX || Math.abs(start.height - end.height) > PAGE_PANE_RESIZE_TOLERANCE_PX;

const animatePagePaneItems = (origin: PagePaneItemPositions, current: PagePaneItemPositions, target: PagePaneItemPositions, timing: KeyframeAnimationOptions): Animation[] => {
    const animations: Animation[] = [];
    for (const [item, start] of origin) {
        const end = target.get(item);
        const now = current.get(item);
        if (end === undefined || now === undefined) continue;
        const first = { x: start.x - now.x, y: start.y - now.y };
        const last = { x: end.x - now.x, y: end.y - now.y };
        if (![first.x, first.y, last.x, last.y].every((value) => Math.abs(value) <= PAGE_PANE_ITEM_TOLERANCE_PX)) animations.push(item.animate([{ translate: `${String(first.x)}px ${String(first.y)}px` }, { translate: `${String(last.x)}px ${String(last.y)}px` }], timing));
        if (!isPagePaneItemResized(start, end)) continue;
        const opacity = Number.parseFloat(getComputedStyleStrict(item).opacity);
        animations.push(
            item.animate(
                [
                    { offset: 0, opacity: 0 },
                    { offset: PAGE_PANE_FADE_IN_END, opacity },
                    { offset: 1, opacity }
                ],
                timing
            )
        );
    }
    for (const animation of animations) animation.pause();
    return animations;
};

export { animatePagePaneItems, isPagePaneItemResized, measurePagePaneItemOrigin, measurePagePaneItems, resolvePagePaneSection };
export type { PagePaneItemBox, PagePaneItemPositions };
