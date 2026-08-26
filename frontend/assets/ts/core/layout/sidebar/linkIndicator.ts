/* SoAI - Shared layout link indicator [frontend/assets/ts/core/layout/sidebar/linkIndicator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ARIA_HIDDEN_ATTR, resolveHTMLElement } from '@core/layout/sidebar/dom.ts';

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
        const link = this.#host.getLink();
        const existing = link ? resolveHTMLElement(`.${this.#indicatorClassName}`, link) : null;
        if (!this.#visible) {
            if (existing) dom.remove(existing);
            return;
        }
        if (!link) return;
        const iconButton = resolveHTMLElement('.sidebar-icon-button', link);
        const target = iconButton ?? link;
        if (existing) {
            if (existing.parentElement !== target) {
                dom.appendChild(target, existing);
            }
            this.#applyVariantClassName(existing);
            existing.removeAttribute('hidden');
            return;
        }
        const indicator = dom.create('span', { className: this.#indicatorClassName, [ARIA_HIDDEN_ATTR]: 'true' });
        this.#applyVariantClassName(indicator);
        dom.appendChild(target, indicator);
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

export { SidebarLinkIndicatorController };
export type { SidebarLinkIndicatorHost };
