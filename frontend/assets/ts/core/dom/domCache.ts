/* SoAI - Shared DOM cache [frontend/assets/ts/core/dom/domCache.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DOMContext, DOMQueryRoot } from '@core/dom/types.ts';

export interface DomCache {
    get: (selector: string, context?: DOMContext) => Element | null;
    getAll: (selector: string, context?: DOMContext) => Element[];
    clear: () => void;
    invalidate: (selector: string) => void;
}

export const createDomCache = (getDomDocument: () => Document): DomCache => {
    const documentCaches = new WeakMap<Document, Map<string, Element | Element[]>>();
    const maxDomCacheSize = 200;

    const getDomCacheForDocument = (doc: Document): Map<string, Element | Element[]> => {
        if (!documentCaches.has(doc)) {
            documentCaches.set(doc, new Map());
        }
        const cache = documentCaches.get(doc);
        if (!cache) {
            throw new Error('Dom cache missing expected document entry');
        }
        return cache;
    };

    const buildDocumentCacheKey = (selector: string): string => `${selector}@d`;

    const evictIfNeeded = (cache: Map<string, Element | Element[]>): void => {
        if (cache.size < maxDomCacheSize) return;
        const firstKey = cache.keys().next().value;
        if (typeof firstKey === 'string') {
            cache.delete(firstKey);
        }
    };

    const resolveActiveContext = (context: DOMContext): DOMQueryRoot => {
        const doc = getDomDocument();
        return context ?? doc;
    };

    return {
        get(selector: string, context?: DOMContext): Element | null {
            const doc = getDomDocument();
            const activeContext = resolveActiveContext(context);
            const isDoc = activeContext === doc;
            if (!isDoc) {
                return activeContext.querySelector(selector);
            }
            const domCacheStore = getDomCacheForDocument(doc);
            const key = buildDocumentCacheKey(selector);
            const cached = domCacheStore.get(key);

            if (cached) {
                if (Array.isArray(cached)) {
                    domCacheStore.delete(key);
                } else if (cached.isConnected) {
                    domCacheStore.delete(key);
                    domCacheStore.set(key, cached);
                    return cached;
                } else {
                    domCacheStore.delete(key);
                }
            }

            const result = activeContext.querySelector(selector);
            if (result) {
                evictIfNeeded(domCacheStore);
                domCacheStore.set(key, result);
            }
            return result;
        },
        getAll(selector: string, context?: DOMContext): Element[] {
            const doc = getDomDocument();
            const activeContext = resolveActiveContext(context);
            const isDoc = activeContext === doc;
            if (!isDoc) {
                return Array.from(activeContext.querySelectorAll(selector));
            }
            const domCacheStore = getDomCacheForDocument(doc);
            const key = buildDocumentCacheKey(`a:${selector}`);
            const cached = domCacheStore.get(key);

            if (cached) {
                if (Array.isArray(cached)) {
                    const allConnected = cached.every((element) => element.isConnected);
                    if (allConnected) {
                        domCacheStore.delete(key);
                        domCacheStore.set(key, cached);
                        return cached;
                    }
                    domCacheStore.delete(key);
                } else {
                    domCacheStore.delete(key);
                }
            }

            const result = Array.from(activeContext.querySelectorAll(selector));
            if (result.length > 0) {
                evictIfNeeded(domCacheStore);
                domCacheStore.set(key, result);
            }
            return result;
        },
        clear(): void {
            const doc = getDomDocument();
            const cache = documentCaches.get(doc);
            if (cache) cache.clear();
        },
        invalidate(selector: string): void {
            const doc = getDomDocument();
            const cache = documentCaches.get(doc);
            if (cache) {
                for (const key of cache.keys()) {
                    if (key.includes(selector)) cache.delete(key);
                }
            }
        }
    };
};
