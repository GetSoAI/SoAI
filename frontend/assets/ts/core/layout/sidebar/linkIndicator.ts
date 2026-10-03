/* SoAI - Shared layout link indicator [frontend/assets/ts/core/layout/sidebar/linkIndicator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, removeWithPresence } from '@core/animations/presence/public.ts';
import { dom } from '@core/dom/dom.ts';
import { ARIA_HIDDEN_ATTR, resolveHTMLElement } from '@core/layout/sidebar/dom.ts';

const syncSidebarLinkIndicator = (link: HTMLElement | null, className: string, visible: boolean): HTMLElement | null => {
    const existing = link ? resolveHTMLElement(`.${className}`, link) : null;
    if (!visible || !link) {
        if (existing) removeWithPresence(existing);
        return null;
    }
    const target = resolveHTMLElement('.sidebar-icon-button', link) ?? link;
    if (existing && existing.parentElement !== target) {
        dom.appendChild(target, existing);
    }
    const indicator = existing ?? dom.create('span', { className, [ARIA_HIDDEN_ATTR]: 'true' });
    insertWithPresence(target, indicator);
    indicator.removeAttribute('hidden');
    return indicator;
};

interface SidebarLinkIndicatorHost {
    getLink: () => HTMLElement | null;
}

class SidebarLinkIndicatorController {
    readonly #host: SidebarLinkIndicatorHost;
    readonly #indicatorClassName: string;
    #variantClassName: string | null = null;
    #visible: boolean = false;

    constructor(options: { host: SidebarLinkIndicatorHost; indicatorClassName: string }) {
        this.#host = options.host;
        const className = options.indicatorClassName.trim();
        if (!className) {
            throw new Error('Sidebar link indicator requires an indicatorClassName');
        }
        this.#indicatorClassName = className;
    }

    updateIndicator(): void {
        const indicator = syncSidebarLinkIndicator(this.#host.getLink(), this.#indicatorClassName, this.#visible);
        if (indicator) {
            this.#applyVariantClassName(indicator);
        }
    }

    setVisible(visible: boolean): void {
        if (this.#visible === visible) return;
        this.#visible = visible;
        this.updateIndicator();
    }

    setVariantClassName(className: string | null): void {
        const normalizedClassName = typeof className === 'string' && className.trim() ? className.trim() : null;
        if (this.#variantClassName === normalizedClassName) return;
        const previousClassName = this.#variantClassName;
        this.#variantClassName = normalizedClassName;
        const link = this.#host.getLink();
        const indicator = link ? resolveHTMLElement(`.${this.#indicatorClassName}`, link) : null;
        if (indicator) {
            if (previousClassName !== null) {
                indicator.classList.remove(previousClassName);
            }
            this.#applyVariantClassName(indicator);
        }
    }

    #applyVariantClassName(indicator: HTMLElement): void {
        if (this.#variantClassName !== null) {
            indicator.classList.add(this.#variantClassName);
        }
    }
}

export { SidebarLinkIndicatorController, syncSidebarLinkIndicator };
export type { SidebarLinkIndicatorHost };
