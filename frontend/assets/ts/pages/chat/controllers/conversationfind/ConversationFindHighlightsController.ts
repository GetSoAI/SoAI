/* SoAI - Document-owned find highlights, clipped pop and mounted minimap marks [frontend/assets/ts/pages/chat/controllers/conversationfind/ConversationFindHighlightsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { animateElementScroll } from '@core/animations/scrollMotion.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { dom } from '@core/dom/dom.ts';
import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { measureLayoutBox, measureLayoutRectangles, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { calculateScrollTopForBand, scrollElementTo } from '@core/scroll.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { projectAdvancedScrollPosition, readMessagesAreaVisibleInsets, type ConversationFindTarget, type ConversationFindResultIndex, type MainTimelineCoordinator, type MountedConversationFindIndex } from '@features/chat/public.ts';

interface ConversationFindHighlightsControllerDependencies {
    area: HTMLElement;
    layer: HTMLElement;
    minimap: HTMLElement;
    coordinator: MainTimelineCoordinator;
    mounted: MountedConversationFindIndex;
}

class ConversationFindHighlightsController {
    readonly #dependencies: ConversationFindHighlightsControllerDependencies;
    readonly #normalName = 'soai-conversation-find';
    readonly #activeName = 'soai-conversation-find-active';
    #normal: Highlight | null = null;
    #active: Highlight | null = null;
    #activeRange: Range | null = null;
    #popUntil = 0;
    #painted: readonly Range[] = [];
    #moving = false;

    constructor(dependencies: ConversationFindHighlightsControllerDependencies) {
        this.#dependencies = dependencies;
    }

    clear(): void {
        const view = this.#dependencies.area.ownerDocument.defaultView;
        if (view?.CSS?.highlights) {
            if (view.CSS.highlights.get(this.#normalName) === this.#normal) view.CSS.highlights.delete(this.#normalName);
            if (view.CSS.highlights.get(this.#activeName) === this.#active) view.CSS.highlights.delete(this.#activeName);
        }
        this.#normal = null;
        this.#active = null;
        this.#activeRange = null;
        this.#painted = [];
        this.#popUntil = 0;
        this.#dependencies.layer.replaceChildren();
        this.#dependencies.minimap.replaceChildren();
        this.#dependencies.coordinator.cancelFrame('conversation-find-geometry');
    }

    async paint(index: ConversationFindResultIndex, target: ConversationFindTarget | null, signal: AbortSignal, isCurrent: () => boolean): Promise<void> {
        const { area, mounted } = this.#dependencies;
        const areaBox = measureLayoutBox(area);
        const entries = index.entries
            .flatMap((entry) => {
                const body = mounted.body(entry.messageId);
                return body ? [{ messageId: entry.messageId, distance: Math.abs(measureLayoutBox(body).top - areaBox.top - area.clientHeight / 2) }] : [];
            })
            .sort((left, right) => left.distance - right.distance);
        const activeRange = target ? await mounted.range(target, signal) : null;
        const ranges = await mounted.paintedRanges(
            entries.map((entry) => entry.messageId),
            activeRange ? 4999 : 5000,
            signal
        );
        if (!isCurrent() || signal.aborted) return;
        this.#painted = ranges;
        this.#activeRange = activeRange;
        const view = area.ownerDocument.defaultView;
        if (view && typeof view.Highlight === 'function' && view.CSS?.highlights) {
            this.#normal = new view.Highlight(...ranges);
            this.#active = new view.Highlight(...(activeRange ? [activeRange] : []));
            this.#normal.priority = 0;
            this.#active.priority = 1;
            view.CSS.highlights.set(this.#normalName, this.#normal);
            view.CSS.highlights.set(this.#activeName, this.#active);
        }
    }

    beginMovement(): () => void {
        return this.#dependencies.coordinator.beginProgrammaticScroll();
    }

    async move(range: Range, isCurrent: () => boolean, signal: AbortSignal): Promise<void> {
        const { area } = this.#dependencies;
        if (!isCurrent() || !range.startContainer.isConnected) return;
        await this.#revealHorizontal(range, isCurrent, signal);
        if (!isCurrent() || signal.aborted || !range.startContainer.isConnected) return;
        const areaBox = measureLayoutBox(area);
        const insets = readMessagesAreaVisibleInsets(area);
        const rectangles = measureLayoutRectangles(range).filter((rectangle) => rectangle.width > 0 && rectangle.height > 0);
        const first = rectangles[0];
        if (!first) return;
        const bounds = measureLayoutBox(range);
        const bandHeight = Math.max(0, area.clientHeight - insets.top - insets.bottom);
        const top = calculateScrollTopForBand({ viewportTop: areaBox.top, viewportHeight: area.clientHeight, scrollTop: area.scrollTop, scrollHeight: area.scrollHeight }, bounds.height > bandHeight ? first : bounds, { topInset: insets.top, bottomInset: insets.bottom, onlyIfOutside: true, oversizedPlacement: 'start' });
        const distance = Math.abs(top - area.scrollTop);
        if (distance > 0 && isCurrent()) {
            this.#moving = true;
            await this.#dependencies.coordinator.scrollTo(top, signal);
            this.#moving = false;
            if (!isCurrent() || !range.startContainer.isConnected) return;
        }
        this.#activeRange = range;
        if (this.#active) {
            this.#active.clear();
            this.#active.add(range);
        }
        this.#popUntil = monotonicMs() + (prefersReducedMotion(area) ? 0 : 450);
        this.#dependencies.layer.classList.remove('conversation-find-pop-layer--playing');
    }

    async #revealHorizontal(range: Range, isCurrent: () => boolean, signal: AbortSignal): Promise<void> {
        const { area } = this.#dependencies;
        for (let element = range.startContainer.parentElement; element && element !== area; element = element.parentElement) {
            if (!isCurrent() || signal.aborted || !element.isConnected) return;
            if (element.scrollWidth <= element.clientWidth) continue;
            const style = getComputedStyleStrict(element);
            if (!['auto', 'scroll', 'hidden'].includes(style.overflowX)) continue;
            const box = measureLayoutBox(element);
            const bounds = measureLayoutBox(range);
            const leftEdge = box.left + element.clientLeft;
            const rightEdge = leftEdge + element.clientWidth;
            const offset = bounds.width > element.clientWidth ? (style.direction === 'rtl' ? bounds.right - rightEdge : bounds.left - leftEdge) : bounds.left < leftEdge ? bounds.left - leftEdge : Math.max(0, bounds.right - rightEdge);
            const maximum = element.scrollWidth - element.clientWidth;
            const left = style.direction === 'rtl' ? Math.max(-maximum, Math.min(0, element.scrollLeft + offset)) : Math.max(0, Math.min(maximum, element.scrollLeft + offset));
            await animateElementScroll(element, { left }, signal);
        }
    }

    stopMovement(): void {
        if (!this.#moving) return;
        this.#moving = false;
        const { area } = this.#dependencies;
        scrollElementTo(area, { top: area.scrollTop, behavior: 'instant' });
    }

    scheduleGeometry(isCurrent: () => boolean, includeMinimap = false): void {
        const { coordinator, area, layer, minimap } = this.#dependencies;
        coordinator.scheduleFrame('conversation-find-geometry', () => {
            if (!isCurrent()) return null;
            const areaBox = measureLayoutBox(area);
            const layerBox = measureLayoutBox(layer);
            const insets = readMessagesAreaVisibleInsets(area);
            const pop = this.#activeRange?.startContainer.isConnected ? measureLayoutRectangles(this.#activeRange) : [];
            const fallback = this.#active === null && this.#activeRange !== null;
            const showPop = fallback || this.#popUntil > monotonicMs();
            const clipped = pop.flatMap((rectangle) => {
                const top = Math.max(rectangle.top, areaBox.top + insets.top);
                const bottom = Math.min(rectangle.bottom, areaBox.top + area.clientHeight - insets.bottom);
                const left = Math.max(rectangle.left, areaBox.left);
                const right = Math.min(rectangle.right, areaBox.right);
                return bottom > top && right > left ? [{ top: top - layerBox.top, left: left - layerBox.left, width: right - left, height: bottom - top }] : [];
            });
            const marks = new Map<number, boolean>();
            if (includeMinimap) {
                for (const range of this.#painted) {
                    if (!range.startContainer.isConnected) continue;
                    for (const rectangle of measureLayoutRectangles(range)) {
                        if (rectangle.width <= 0 || rectangle.height <= 0 || area.scrollHeight <= 0) continue;
                        const top = Math.round(projectAdvancedScrollPosition(rectangle.top - areaBox.top + area.scrollTop, area.scrollHeight, minimap.clientHeight));
                        const bottom = Math.round(projectAdvancedScrollPosition(rectangle.bottom - areaBox.top + area.scrollTop, area.scrollHeight, minimap.clientHeight));
                        for (let row = top; row <= bottom; row += 1) marks.set(row, false);
                    }
                }
                if (this.#activeRange?.startContainer.isConnected && area.scrollHeight > 0) {
                    const rectangle = measureLayoutBox(this.#activeRange);
                    marks.set(Math.round(projectAdvancedScrollPosition(rectangle.top - areaBox.top + area.scrollTop, area.scrollHeight, minimap.clientHeight)), true);
                }
            }
            return () => {
                if (!isCurrent()) return;
                this.#writeRectangles(layer, showPop ? clipped : []);
                layer.classList.toggle('conversation-find-pop-layer--playing', showPop);
                layer.classList.toggle('conversation-find-pop-layer--fallback', fallback);
                if (includeMinimap) {
                    minimap.replaceChildren(
                        ...Array.from(marks, ([top, active]) => {
                            const mark = area.ownerDocument.createElement('span');
                            mark.className = active ? 'conversation-find-mark conversation-find-mark--active' : 'conversation-find-mark';
                            dom.setStyle(mark, '--find-mark-top', `${top}px`);
                            return mark;
                        })
                    );
                }
            };
        });
    }

    #writeRectangles(layer: HTMLElement, rectangles: readonly Pick<GeometryBox, 'left' | 'top' | 'width' | 'height'>[]): void {
        while (layer.children.length > rectangles.length) layer.lastElementChild?.remove();
        for (let index = 0; index < rectangles.length; index += 1) {
            const rectangle = rectangles[index];
            if (!rectangle) continue;
            let element = layer.children.item(index);
            if (!(element instanceof HTMLElement)) {
                element = layer.ownerDocument.createElement('span');
                element.className = 'conversation-find-pop';
                layer.append(element);
            }
            dom.setStyles(element, { '--find-rect-left': `${rectangle.left}px`, '--find-rect-top': `${rectangle.top}px`, '--find-rect-width': `${rectangle.width}px`, '--find-rect-height': `${rectangle.height}px` });
        }
    }
}

export { ConversationFindHighlightsController };
export type { ConversationFindHighlightsControllerDependencies };
