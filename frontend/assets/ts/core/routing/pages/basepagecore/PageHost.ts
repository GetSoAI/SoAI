/* SoAI - Routed page container and section ownership [frontend/assets/ts/core/routing/pages/basepagecore/PageHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isHTMLElement } from '@core/typeGuards.ts';

class PageHost {
    readonly pageId: string;
    #container: HTMLElement | null = null;

    constructor(pageId: string) {
        this.pageId = pageId;
    }

    get container(): HTMLElement | null {
        return this.#container;
    }

    setContainer(container: HTMLElement): void {
        if (!isHTMLElement(container)) throw new TypeError(`Page ${this.pageId} requires valid container`);
        this.#container = container;
    }

    clearContainer(): void {
        this.#container = null;
    }

    resolveContainer(): HTMLElement {
        if (this.#container) return this.#container;
        const host = dom.resolve('#main-content') || dom.resolve('body');
        if (!isHTMLElement(host)) throw new Error('Page container unavailable');
        this.#container = host;
        return host;
    }

    getContext(): Element | null {
        return this.#container;
    }

    getSection(): HTMLElement | null {
        const section = dom.resolve(`[data-section="${this.pageId}"]`, this.resolveContainer());
        return isHTMLElement(section) ? section : null;
    }
}

export { PageHost };
