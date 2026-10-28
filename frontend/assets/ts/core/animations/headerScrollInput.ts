/* SoAI - User scroll input ownership for floating page headers [frontend/assets/ts/core/animations/headerScrollInput.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEditableKeyboardTarget } from '@core/dom/editableTargets.ts';
import { measureScrollEdges } from '@core/dom/scrollGeometry.ts';
import { getComputedStyleStrict, getWindow } from '@core/environment/public.ts';
import { measureViewportTouchPoint } from '@core/layout/elementGeometry.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';

type HeaderScrollInputDirection = 'up' | 'down' | 'scrollbar' | null;
type VerticalInputDirection = 'up' | 'down' | null;

const scrollReachesContainer = (container: HTMLElement, target: EventTarget | null, direction: VerticalInputDirection): boolean => {
    if (!(target instanceof Node)) return false;
    if (target === container.ownerDocument.body) return true;
    for (let element = target instanceof Element ? target : target.parentElement; element !== null && element !== container; element = element.parentElement) {
        if (element.scrollHeight <= element.clientHeight) continue;
        const style = getComputedStyleStrict(element);
        if (!['auto', 'scroll', 'overlay'].includes(style.overflowY)) continue;
        const edges = measureScrollEdges({ position: element.scrollTop, extent: element.scrollHeight, viewport: element.clientHeight, tolerance: 1 });
        if ((direction === 'up' && !edges.atStart) || (direction === 'down' && !edges.atEnd) || style.overscrollBehaviorY === 'contain' || style.overscrollBehaviorY === 'none') return false;
    }
    return container.contains(target);
};

const allowsVerticalTouch = (container: HTMLElement, target: EventTarget | null): boolean => {
    if (!(target instanceof Node)) return false;
    for (let element = target instanceof Element ? target : target.parentElement; element !== null; element = element.parentElement) {
        const action = getComputedStyleStrict(element).getPropertyValue('touch-action');
        if (action === 'none' || ((action.includes('pan-') || action === 'pinch-zoom') && !/pan-(y|up|down)/.test(action))) return false;
        if (element === container) return true;
    }
    return false;
};

const readTouchPosition = (event: TouchEvent): number | null => {
    const touch = event.touches.length === 1 ? event.touches.item(0) : null;
    return touch === null ? null : measureViewportTouchPoint(touch).y;
};

class HeaderScrollInput {
    readonly #container: HTMLElement;
    readonly #onScrollToStart: () => void;
    #direction: VerticalInputDirection = null;
    #scrollbarPointer: number | null = null;
    #touchPosition: number | null = null;
    #touchInitialScrollTop = 0;
    #hasScrolledSinceInput = false;

    constructor(container: HTMLElement, resources: ResourceTracker, onScrollToStart: () => void) {
        this.#container = container;
        this.#onScrollToStart = onScrollToStart;
        resources.addEventListener(
            container,
            'wheel',
            (event: Event) => {
                if (!(typeof WheelEvent === 'function' && event instanceof WheelEvent)) return;
                this.#setDirection(event.defaultPrevented || event.ctrlKey || event.deltaY === 0 ? null : event.deltaY > 0 ? 'down' : 'up', event.target);
            },
            { passive: true }
        );
        resources.addEventListener(container.ownerDocument, 'keydown', (event: Event) => {
            if (!(typeof KeyboardEvent === 'function' && event instanceof KeyboardEvent)) return;
            const target = event.target;
            if (!(target instanceof Node) || (!container.contains(target) && !(target === container.ownerDocument.body && container.getClientRects().length > 0))) return;
            let direction: VerticalInputDirection = null;
            const scrollModifier = !event.altKey && (!(event.ctrlKey || event.metaKey) || ['Home', 'End', 'ArrowUp', 'ArrowDown'].includes(event.key));
            if (!event.defaultPrevented && scrollModifier && !isEditableKeyboardTarget(target)) {
                if (event.key === 'ArrowDown' || event.key === 'PageDown' || event.key === 'End') direction = 'down';
                else if (event.key === 'ArrowUp' || event.key === 'PageUp' || event.key === 'Home') direction = 'up';
                else if (event.key === ' ' && !(target instanceof Element && target.closest('button, [role="button"], summary'))) direction = event.shiftKey ? 'up' : 'down';
            }
            this.#setDirection(direction, target);
        });
        resources.addEventListener(
            container,
            'pointerdown',
            (event: Event) => {
                if (!(typeof PointerEvent === 'function' && event instanceof PointerEvent)) return;
                this.clearScrollDirection();
                this.#scrollbarPointer = event.target === container && event.pointerType !== 'touch' && event.button === 0 ? event.pointerId : null;
            },
            { passive: true }
        );
        const finishPointer = (event: Event): void => {
            if (!(typeof PointerEvent === 'function' && event instanceof PointerEvent)) return;
            if (this.#scrollbarPointer === event.pointerId) this.#scrollbarPointer = null;
        };
        resources.addEventListener(container.ownerDocument, 'pointerup', finishPointer, { passive: true });
        resources.addEventListener(container.ownerDocument, 'pointercancel', finishPointer, { passive: true });
        const cancelInput = (): void => {
            this.clearScrollDirection();
            this.#scrollbarPointer = null;
            this.#touchPosition = null;
        };
        resources.addEventListener(getWindow(), 'blur', cancelInput);
        resources.addEventListener(container.ownerDocument, 'visibilitychange', () => {
            if (container.ownerDocument.hidden) cancelInput();
        });
        resources.addEventListener(
            container,
            'touchstart',
            (event: Event) => {
                if (!(typeof TouchEvent === 'function' && event instanceof TouchEvent)) return;
                this.clearScrollDirection();
                this.#touchInitialScrollTop = container.scrollTop;
                this.#touchPosition = event.defaultPrevented || !allowsVerticalTouch(container, event.target) ? null : readTouchPosition(event);
            },
            { passive: true }
        );
        resources.addEventListener(
            container,
            'touchmove',
            (event: Event) => {
                if (!(typeof TouchEvent === 'function' && event instanceof TouchEvent)) return;
                if (this.#touchPosition === null) return;
                const position = event.defaultPrevented ? null : readTouchPosition(event);
                const direction = position !== null && this.#touchPosition !== null && position !== this.#touchPosition ? (this.#touchPosition > position ? 'down' : 'up') : null;
                this.#setDirection(direction, event.target);
                this.#touchPosition = position;
            },
            { passive: true }
        );
        const finishTouch = (event: Event): void => {
            if (!(typeof TouchEvent === 'function' && event instanceof TouchEvent)) return;
            if (event.touches.length !== 0) return;
            this.#touchPosition = null;
            if (container.scrollTop === this.#touchInitialScrollTop) this.clearScrollDirection();
        };
        resources.addEventListener(container, 'touchend', finishTouch, { passive: true });
        resources.addEventListener(container, 'touchcancel', finishTouch, { passive: true });
        resources.addEventListener(
            container,
            'scrollend',
            (event: Event) => {
                if (event.target === container && this.#hasScrolledSinceInput) this.clearScrollDirection();
            },
            { passive: true }
        );
    }

    readonly clearScrollDirection = (): void => {
        this.#direction = null;
        this.#hasScrolledSinceInput = false;
    };

    captureDirection(delta: number): HeaderScrollInputDirection {
        if ((this.#direction === 'up' && delta < 0) || (this.#direction === 'down' && delta > 0)) this.#hasScrolledSinceInput = true;
        return this.#scrollbarPointer !== null ? 'scrollbar' : this.#direction;
    }

    #setDirection(direction: VerticalInputDirection, target: EventTarget | null): void {
        this.#hasScrolledSinceInput = false;
        this.#direction = direction !== null && scrollReachesContainer(this.#container, target, direction) ? direction : null;
        if (this.#direction === 'up' && this.#container.scrollTop <= 0) this.#onScrollToStart();
    }
}

export { HeaderScrollInput };
export type { HeaderScrollInputDirection };
