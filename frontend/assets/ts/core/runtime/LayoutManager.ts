/* SoAI - Shared runtime layout manager [frontend/assets/ts/core/runtime/LayoutManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { hasFunctionProperties, isArray, isHTMLElement, isObject, isString } from '@core/typeGuards.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

const DEFAULT_LAYER_TAG = 'div';

interface LayerOptions {
    selector?: string;
    tagName?: string;
    id?: string | null;
    className?: string | null;
    attributes?: Record<string, string>;
    dataset?: Record<string, string>;
}

class LayoutRuntimeManager {
    private bodyRef: HTMLElement | null;
    private layerCache: Map<string, HTMLElement>;

    constructor() {
        this.bodyRef = null;
        this.layerCache = new Map();
    }

    getDocument(): Document {
        return dom.getDocument();
    }

    getRootElement(): HTMLElement {
        return dom.getDocumentElement();
    }

    getBody(): HTMLElement {
        if (this.bodyRef?.isConnected) {
            return this.bodyRef;
        }
        const body = dom.getBody();
        this.bodyRef = body;
        return body;
    }

    refreshBody(): HTMLElement {
        this.bodyRef = null;
        return this.getBody();
    }

    addBodyClass(classes: string | string[]): void {
        if (!classes) {
            return;
        }
        dom.addClass(this.getBody(), classes);
    }

    removeBodyClass(classes: string | string[]): void {
        if (!classes) {
            return;
        }
        dom.removeClass(this.getBody(), classes);
    }

    setBodyClass(name: string, enabled: boolean): void {
        if (!name) {
            return;
        }
        dom.toggleClass(this.getBody(), name, enabled);
    }

    hasBodyClass(name: string): boolean {
        if (!name) {
            return false;
        }
        const body = this.getBody();
        return Boolean(body?.classList?.contains(name));
    }

    setBodyAttribute(name: string, value: string | null): void {
        if (!name) {
            return;
        }
        dom.setAttribute(this.getBody(), name, value ?? null);
    }

    removeBodyAttribute(name: string): void {
        if (!name) {
            return;
        }
        dom.setAttribute(this.getBody(), name, null);
    }

    setBodyStyle(property: string, value: string): void {
        if (!property) {
            return;
        }
        dom.setStyle(this.getBody(), property, value);
    }

    setBodyStyles(styles: Record<string, string>): void {
        if (!isObject(styles)) {
            return;
        }
        dom.setStyles(this.getBody(), styles);
    }

    clearBodyStyle(property: string): void {
        if (!property) {
            return;
        }
        dom.setStyle(this.getBody(), property, '');
    }

    clearBodyStyles(properties: string | string[] = []): void {
        if (!properties) {
            return;
        }
        const list = isArray(properties) ? properties : [properties];
        list.forEach((prop) => this.clearBodyStyle(prop));
    }

    appendToBody(nodes: Node | Node[]): void {
        if (!nodes) {
            return;
        }
        dom.appendChild(this.getBody(), nodes);
    }

    removeNode(node: Node): void {
        if (!node) {
            return;
        }
        if (node instanceof Element) {
            dom.remove(node);
            return;
        }
        node.parentNode?.removeChild(node);
    }

    #normalizeLayerKey(key: string): string {
        const normalized = toTrimmedString(key ?? '');
        if (!normalized) {
            throw new Error('Layout layer key must be a non-empty string');
        }
        return normalized;
    }

    #resolveCachedLayer(key: string): HTMLElement | null {
        const cached = this.layerCache.get(key);
        if (cached?.isConnected) {
            return cached;
        }
        if (cached) {
            this.layerCache.delete(key);
        }
        return null;
    }

    ensureLayer(key: string, options: LayerOptions = {}): HTMLElement {
        const normalizedKey = this.#normalizeLayerKey(key);
        const cached = this.#resolveCachedLayer(normalizedKey);
        if (cached) {
            return cached;
        }
        const body = this.getBody();
        const selector = isString(options.selector) ? options.selector.trim() : '';
        if (selector) {
            const existing = dom.resolve(selector, body);
            if (isHTMLElement(existing)) {
                this.layerCache.set(normalizedKey, existing);
                return existing;
            }
        }
        const tagName = isString(options.tagName) && options.tagName.trim() ? options.tagName.trim() : DEFAULT_LAYER_TAG;
        const element = dom.create(tagName, {
            ...(options.id ? { id: options.id } : {}),
            ...(options.className ? { className: options.className } : {})
        });
        dom.setData(element, 'layout-layer', normalizedKey);
        if (isObject(options.attributes)) {
            Object.entries(options.attributes).forEach(([attr, value]) => dom.setAttribute(element, attr, value));
        }
        if (isObject(options.dataset)) {
            Object.entries(options.dataset).forEach(([name, value]) => dom.setData(element, name, value));
        }
        dom.appendChild(body, element);
        this.layerCache.set(normalizedKey, element);
        return element;
    }

    appendToLayer(key: string, nodes: Node | Node[], options: LayerOptions = {}): HTMLElement | null {
        if (!nodes) {
            return null;
        }
        const layer = this.ensureLayer(key, options);
        if (!layer) {
            errorHandler.warn('LayoutRuntimeManager', `Failed to resolve layer ${key}`);
            return null;
        }
        dom.appendChild(layer, nodes);
        return layer;
    }

    removeLayer(key: string): void {
        const normalizedKey = this.#normalizeLayerKey(key);
        const layer = this.#resolveCachedLayer(normalizedKey);
        if (layer) {
            dom.remove(layer);
        }
        this.layerCache.delete(normalizedKey);
    }

    mountOverlay(nodes: Node | Node[]): HTMLElement | null {
        return this.appendToLayer('overlays', nodes, {
            className: 'layout-overlay-layer',
            selector: '[data-layout-layer="overlays"]'
        });
    }
}

const LAYOUT_RUNTIME_SERVICE_ID = 'core.layoutManager';

const isLayoutRuntimeManager = <T>(value: T): value is T & LayoutRuntimeManager => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperties(value, ['ensureLayer', 'appendToLayer', 'removeLayer', 'mountOverlay']);
};

const createLayoutRuntimeManager = (): LayoutRuntimeManager => new LayoutRuntimeManager();

const getLayoutRuntimeManager = (): LayoutRuntimeManager => {
    const candidate = resolveKernelService(LAYOUT_RUNTIME_SERVICE_ID);
    if (!isLayoutRuntimeManager(candidate)) {
        throw new Error(`${LAYOUT_RUNTIME_SERVICE_ID} is not registered`);
    }
    return candidate;
};

export { LayoutRuntimeManager, createLayoutRuntimeManager, getLayoutRuntimeManager, LAYOUT_RUNTIME_SERVICE_ID };

export type { LayerOptions };
