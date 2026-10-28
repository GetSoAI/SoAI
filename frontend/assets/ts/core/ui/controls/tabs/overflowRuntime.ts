/* SoAI - Shared tab strip overflow navigation runtime [frontend/assets/ts/core/ui/controls/tabs/overflowRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createOverflowNavButton, OverflowNavController, type OverflowNavDirection } from '@core/ui/controls/OverflowNav.ts';

const TABS_NAV_SELECTOR = '.tabs-nav-wrapper > .tabs-nav';

interface TabsOverflowRuntimeService {
    initialize: () => void;
    dispose: () => void;
}

const resolveTabsNavButton = (wrapper: HTMLElement, nav: HTMLElement, direction: OverflowNavDirection): HTMLElement => {
    const existing = dom.resolve(`:scope > .tabs-nav-button--${direction}`, wrapper);
    if (existing instanceof HTMLElement) {
        return existing;
    }
    const button = createOverflowNavButton(wrapper.ownerDocument, {
        direction,
        className: `tabs-nav-button tabs-nav-button--${direction}`,
        iconName: direction === 'left' ? 'chevron-left' : 'chevron-right',
        iconOptions: { size: 24, strokeWidth: 1.5 }
    });
    if (direction === 'left') {
        dom.insertBefore(wrapper, button, nav);
    } else {
        dom.insertBefore(wrapper, button, nav.nextElementSibling);
    }
    return button;
};

class TabsOverflowRuntime implements TabsOverflowRuntimeService {
    readonly #documentRef: Document;
    readonly #resources = new ResourceTracker();
    readonly #controllers = new Map<HTMLElement, OverflowNavController>();
    #observer: MutationObserver | null = null;

    constructor(documentRef: Document) {
        this.#documentRef = documentRef;
    }

    initialize(): void {
        const view = this.#documentRef.defaultView;
        if (this.#observer || !view) {
            return;
        }
        this.#observer = new view.MutationObserver(this.#handleRecords);
        this.#observer.observe(this.#documentRef.body, { childList: true, subtree: true });
        if (this.#bindWithin(this.#documentRef.body)) {
            dom.flush();
        }
    }

    dispose(): void {
        this.#observer?.disconnect();
        this.#observer = null;
        for (const controller of this.#controllers.values()) {
            controller.dispose();
        }
        this.#controllers.clear();
    }

    readonly #handleRecords = (records: MutationRecord[]): void => {
        let removedNodes = false;
        let boundNavs = false;
        for (const record of records) {
            record.addedNodes.forEach((node) => {
                if (node instanceof HTMLElement && this.#bindWithin(node)) {
                    boundNavs = true;
                }
            });
            removedNodes ||= record.removedNodes.length > 0;
        }
        if (removedNodes) {
            this.#releaseDetached();
        }
        if (boundNavs) {
            dom.flush();
        }
    };

    #bindWithin(root: HTMLElement): boolean {
        const candidates = root.matches(TABS_NAV_SELECTOR) ? [root] : root.firstElementChild === null ? [] : dom.resolveAll(TABS_NAV_SELECTOR, root);
        let bound = false;
        for (const nav of candidates) {
            const wrapper = nav.parentElement;
            if (nav instanceof HTMLElement && wrapper instanceof HTMLElement && !this.#controllers.has(nav)) {
                this.#bind(wrapper, nav);
                bound = true;
            }
        }
        return bound;
    }

    #bind(wrapper: HTMLElement, nav: HTMLElement): void {
        const controller = new OverflowNavController(nav, resolveTabsNavButton(wrapper, nav, 'left'), resolveTabsNavButton(wrapper, nav, 'right'), {
            onUpdate: (state) => dom.toggleClass(wrapper, 'is-overflowing', state.canScrollLeft || state.canScrollRight)
        });
        controller.initialize((target, type, listener, options) => this.#resources.addEventListener(target, type, listener, options));
        this.#controllers.set(nav, controller);
    }

    #releaseDetached(): void {
        for (const [nav, controller] of this.#controllers) {
            if (!nav.isConnected) {
                controller.dispose();
                this.#controllers.delete(nav);
            }
        }
    }
}

const createTabsOverflowRuntime = (documentRef: Document): TabsOverflowRuntimeService => new TabsOverflowRuntime(documentRef);

export { createTabsOverflowRuntime };
export type { TabsOverflowRuntimeService };
