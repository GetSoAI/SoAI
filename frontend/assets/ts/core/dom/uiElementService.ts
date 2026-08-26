/* SoAI - Shared DOM UI element service [frontend/assets/ts/core/dom/uiElementService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DOMContext } from '@core/dom/types.ts';

interface GetElementOptions {
    cache?: boolean;
    throwOnMissing?: boolean;
}

interface UiElementServiceDependencies {
    getDomDocument: () => Document;
    resolve: (selector: string, context?: DOMContext) => Element | null;
    resolveAll: (selector: string, context?: DOMContext) => Element[];
}

class UIElementService {
    ownerId: string;
    cache: Map<string, Element>;
    #dependencies: UiElementServiceDependencies;

    constructor(ownerId: string, dependencies: UiElementServiceDependencies) {
        this.ownerId = ownerId;
        this.cache = new Map();
        this.#dependencies = dependencies;
    }

    getElement(elementId: string, options: GetElementOptions = {}): Element | null {
        const { cache = true, throwOnMissing = false } = options;
        const doc = this.#dependencies.getDomDocument();

        if (cache && this.cache.has(elementId)) {
            const cached = this.cache.get(elementId);
            if (cached && doc.contains(cached)) {
                return cached;
            }
            this.cache.delete(elementId);
        }

        const selector = elementId.startsWith('#') ? elementId : `#${elementId}`;
        const element = this.resolve(selector);
        if (element && cache) {
            this.cache.set(elementId, element);
        }

        if (!element && throwOnMissing) {
            throw new Error(`Required UI element #${elementId} not found`);
        }

        return element;
    }

    $(selector: string, context?: DOMContext): Element | null {
        return this.resolve(selector, context);
    }

    $$(selector: string, context?: DOMContext): Element[] {
        return this.resolveAll(selector, context);
    }

    resolve(selector: string, context?: DOMContext): Element | null {
        const doc = this.#dependencies.getDomDocument();
        const activeContext = context ?? doc;
        return this.#dependencies.resolve(selector, activeContext);
    }

    resolveAll(selector: string, context?: DOMContext): Element[] {
        const doc = this.#dependencies.getDomDocument();
        const activeContext = context ?? doc;
        const result = this.#dependencies.resolveAll(selector, activeContext);
        return Array.isArray(result) ? result : [];
    }

    clearCache(): void {
        this.cache.clear();
    }

    removeFromCache(elementId: string): void {
        this.cache.delete(elementId);
    }

    getCacheSize(): number {
        return this.cache.size;
    }

    getCachedElements(): string[] {
        return Array.from(this.cache.keys());
    }

    validateCachedElements(): string[] {
        const invalidElements: string[] = [];
        const doc = this.#dependencies.getDomDocument();
        for (const [elementId, element] of this.cache.entries()) {
            if (!doc.contains(element)) {
                invalidElements.push(elementId);
            }
        }

        invalidElements.forEach((elementId) => {
            this.cache.delete(elementId);
        });

        return invalidElements;
    }

    destroy(): void {
        this.cache.clear();
    }
}

const createUIElementServiceFactory =
    (dependencies: UiElementServiceDependencies): ((ownerId: string) => UIElementService) =>
    (ownerId: string): UIElementService =>
        new UIElementService(ownerId, dependencies);

export { UIElementService, createUIElementServiceFactory };
export type { GetElementOptions };
