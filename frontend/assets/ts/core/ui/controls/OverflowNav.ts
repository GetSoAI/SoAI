/* SoAI - Shared UI overflow nav [frontend/assets/ts/core/ui/controls/OverflowNav.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { securityApi } from '@core/security/public.ts';
import { isFiniteNumber, isFunction } from '@core/typeGuards.ts';
import { applyTabsWheelScroll } from '@core/ui/controls/tabs/wheelScroll.ts';
import { getIconSync, type IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';

type OverflowNavDirection = 'left' | 'right';

interface OverflowNavScrollState {
    maxScrollLeft: number;
    currentScroll: number;
    canScrollLeft: boolean;
    canScrollRight: boolean;
}

interface OverflowNavControllerOptions {
    scrollAmount?: number | undefined;
    epsilon?: number | undefined;
    onUpdate?: ((state: { canScrollLeft: boolean; canScrollRight: boolean }) => void) | undefined;
}

const createOverflowNavButtonMarkup = (options: { direction: OverflowNavDirection; className: string; label: string; iconName: IconName; iconOptions?: IconOptions | undefined }): string => {
    const safeLabel = securityApi.escapeAttribute(options.label);
    const iconOptions = options.iconOptions;
    const iconRequest: IconOptions = iconOptions
        ? {
              ...iconOptions,
              attributes: { 'aria-hidden': 'true', focusable: 'false' }
          }
        : {
              attributes: { 'aria-hidden': 'true', focusable: 'false' }
          };
    const iconMarkup = renderIconSlot(getIconSync(options.iconName, iconRequest));
    return `<button type="button" class="${options.className}" aria-label="${safeLabel}" data-tooltip="${safeLabel}">
        ${iconMarkup}
    </button>`;
};

class OverflowNavController {
    #observer: ResizeObserver | null;
    #scrollAmount: number;
    #epsilon: number;
    #onUpdate: OverflowNavControllerOptions['onUpdate'];
    #disposers: Array<() => void>;

    readonly scroller: HTMLElement;
    readonly leftButton: HTMLElement;
    readonly rightButton: HTMLElement;

    constructor(scroller: HTMLElement, leftButton: HTMLElement, rightButton: HTMLElement, options: OverflowNavControllerOptions = {}) {
        this.scroller = scroller;
        this.leftButton = leftButton;
        this.rightButton = rightButton;
        this.#observer = null;
        this.#disposers = [];

        const scrollAmount = options.scrollAmount;
        this.#scrollAmount = isFiniteNumber(scrollAmount) ? scrollAmount : 0.8;
        const epsilon = options.epsilon;
        this.#epsilon = isFiniteNumber(epsilon) ? epsilon : 4;
        this.#onUpdate = isFunction(options.onUpdate) ? options.onUpdate : undefined;
    }

    initialize(addEventListener: (target: EventTarget, type: string, listener: EventListener, options?: AddEventListenerOptions) => () => void): void {
        if (!isFunction(addEventListener)) {
            throw new TypeError('OverflowNavController requires an addEventListener function');
        }

        this.dispose();

        this.#disposers.push(
            addEventListener(
                this.scroller,
                'wheel',
                (event: Event) => {
                    if (!(event instanceof WheelEvent)) {
                        throw new TypeError('OverflowNavController wheel listener requires a WheelEvent');
                    }
                    applyTabsWheelScroll(this.scroller, event, this.#epsilon);
                },
                { passive: false }
            )
        );

        this.#disposers.push(addEventListener(this.scroller, 'scroll', () => this.update()));
        this.#disposers.push(
            addEventListener(this.leftButton, 'click', (error: Event) => {
                error.preventDefault();
                this.scroll(-1);
            })
        );
        this.#disposers.push(
            addEventListener(this.rightButton, 'click', (error: Event) => {
                error.preventDefault();
                this.scroll(1);
            })
        );

        this.#observer = new ResizeObserver(() => this.update());
        this.#observer.observe(this.scroller);

        this.#disposers.push(addEventListener(window, 'resize', () => this.update()));
        this.#disposers.push(addEventListener(window, INTERFACE_SCALE_CHANGED_EVENT, () => this.update()));

        this.update();
    }

    scroll(direction: number): void {
        const state = this.#getScrollState();
        const distance = this.scroller.clientWidth * this.#scrollAmount;
        let value = direction < 0 ? -Math.abs(distance) : Math.abs(distance);

        const targetScroll = state.currentScroll + value;
        if (targetScroll < 0) {
            value = -state.currentScroll;
        } else if (targetScroll > state.maxScrollLeft) {
            value = state.maxScrollLeft - state.currentScroll;
        }

        this.scroller.scrollBy({ left: value, behavior: 'smooth' });
    }

    update(): void {
        const state = this.#getScrollState();
        dom.toggleClass(this.leftButton, 'is-active', state.canScrollLeft);
        dom.setProperty(this.leftButton, 'disabled', !state.canScrollLeft);
        dom.toggleClass(this.rightButton, 'is-active', state.canScrollRight);
        dom.setProperty(this.rightButton, 'disabled', !state.canScrollRight);

        if (this.#onUpdate) {
            this.#onUpdate({ canScrollLeft: state.canScrollLeft, canScrollRight: state.canScrollRight });
        }
    }

    #getScrollState(): OverflowNavScrollState {
        const maxScrollLeft = Math.max(this.scroller.scrollWidth - this.scroller.clientWidth, 0);
        const currentScroll = this.scroller.scrollLeft;
        return {
            maxScrollLeft,
            currentScroll,
            canScrollLeft: currentScroll > this.#epsilon,
            canScrollRight: currentScroll < maxScrollLeft - this.#epsilon
        };
    }

    dispose(): void {
        if (this.#observer) {
            this.#observer.disconnect();
            this.#observer = null;
        }

        for (const disposer of this.#disposers.splice(0)) {
            disposer();
        }
    }
}

export { OverflowNavController, createOverflowNavButtonMarkup };
export type { OverflowNavDirection, OverflowNavControllerOptions };
