/* SoAI - Shared DOM service [frontend/assets/ts/core/dom/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyMap, DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isTrustedHtml, type TrustedHtml } from '@core/security/public.ts';

import { isDocumentFragment } from '@core/dom/domEnvironment.ts';
import type { PerformanceMetrics, DOMContext, DOMTarget, DOMUpdate, ReplaceContentOptions, SetHTMLOptions } from '@core/dom/types.ts';
import type { DOMUpdateServiceRuntime, DomUpdateServiceDependencies, ListenerRegistryEntry, PendingUpdateEntry } from '@core/dom/internalContracts.ts';
import { flushDOMUpdates, queueDOMUpdate } from '@core/dom/effects.ts';
import { cleanupDOMListeners } from '@core/dom/events.ts';
import { normalizeClassList, normalizeNodes } from '@core/dom/mappers.ts';
import { resolveDOMElement } from '@core/dom/adapters/public.ts';

class DOMUpdateService implements DOMUpdateServiceRuntime {
    pendingUpdates: Map<Element | DocumentFragment, PendingUpdateEntry>;
    batchTimer: number | null;
    listenerRegistry: WeakMap<Element, ListenerRegistryEntry[]>;
    updateCounter: number;
    batchingEnabled: boolean;
    performanceMetrics: PerformanceMetrics;
    dependencies: DomUpdateServiceDependencies;

    constructor(dependencies: DomUpdateServiceDependencies) {
        this.dependencies = dependencies;
        this.pendingUpdates = new Map();
        this.batchTimer = null;
        this.listenerRegistry = new WeakMap();
        this.updateCounter = 0;
        this.batchingEnabled = false;
        this.performanceMetrics = {
            totalUpdates: 0,
            batchedUpdates: 0,
            averageBatchSize: 0
        };
    }

    setText(target: DOMTarget, text: JsonValue | string | number | boolean | null | undefined, context: DOMContext = null): void {
        this.#enqueue(target, context, {
            type: 'text',
            value: this.dependencies.toString(text)
        });
    }

    setHTML(target: DOMTarget, html: TrustedHtml | string, options: SetHTMLOptions = {}): void {
        const { escape = true, context = null } = options;
        if (isTrustedHtml(html)) {
            this.#enqueue(target, context, { type: 'html', value: html.html });
            return;
        }
        if (escape) {
            const value = this.dependencies.security.escapeHtml(this.dependencies.toString(html));
            this.#enqueue(target, context, { type: 'html', value });
            return;
        }
        if (!isTrustedHtml(html)) {
            throw new Error('setHTML with escape=false requires TrustedHtml');
        }
    }

    setAttribute(target: DOMTarget, attribute: string, value: string | null, context: DOMContext = null): void {
        this.#enqueue(target, context, { type: 'attribute', attribute, value });
    }

    setStyle(target: DOMTarget, property: string | Record<string, string | null>, value: string | null, context: DOMContext = null): void {
        if (this.dependencies.isString(property)) {
            this.#enqueue(target, context, { type: 'style', property, value });
            return;
        }
        if (!this.dependencies.isPlainObject(property)) {
            throw new TypeError('setStyle property map must be a plain object');
        }
        this.#enqueue(target, context, { type: 'styles', styles: property });
    }

    addClass(target: DOMTarget, classes: string | string[], context: DOMContext = null): void {
        this.#enqueue(target, context, {
            type: 'addClass',
            classes: normalizeClassList(this, classes)
        });
    }

    removeClass(target: DOMTarget, classes: string | string[], context: DOMContext = null): void {
        this.#enqueue(target, context, {
            type: 'removeClass',
            classes: normalizeClassList(this, classes)
        });
    }

    toggleClass(target: DOMTarget, className: string, force: boolean | null = null, context: DOMContext = null): void {
        this.#enqueue(target, context, { type: 'toggleClass', className, force });
    }

    replaceContent(target: DOMTarget, content: string | TrustedHtml | DocumentFragment | HTMLElement, options: ReplaceContentOptions = {}): void {
        const { escape = true, context = null } = options;
        const element = resolveDOMElement(this, target, context);
        if (!element) return;

        if (element instanceof Element) {
            cleanupDOMListeners(this, element);
        }

        if (isTrustedHtml(content)) {
            this.#queueUpdate(element, { type: 'html', value: content.html });
            return;
        }

        if (typeof content === 'string') {
            if (escape === false) {
                throw new Error('replaceContent with escape=false requires TrustedHtml');
            }
            const value = this.dependencies.security.escapeHtml(this.dependencies.toString(content));
            this.#queueUpdate(element, {
                type: 'html',
                value
            });
            return;
        }

        if (!isDocumentFragment(content) && !this.dependencies.isHTMLElement(content)) {
            throw new TypeError('replaceContent requires a DocumentFragment or HTMLElement content node');
        }
        this.#queueUpdate(element, {
            type: 'replaceContent',
            content
        });
    }

    appendChild(target: DOMTarget, children: Node | Node[], context: DOMContext = null): void {
        this.#enqueue(target, context, {
            type: 'appendChild',
            children: normalizeNodes(this, children)
        });
    }

    insertBefore(target: DOMTarget, children: Node | Node[], reference: DOMTarget = null, context: DOMContext = null): void {
        const parent = resolveDOMElement(this, target, context);
        if (!parent) return;

        const childList = normalizeNodes(this, children);
        const referenceCandidate = reference ? resolveDOMElement(this, reference, parent) : null;
        const referenceNode = referenceCandidate && this.dependencies.isNode(referenceCandidate) && parent.contains(referenceCandidate) ? referenceCandidate : null;

        this.#queueUpdate(parent, {
            type: 'insertBefore',
            children: childList,
            reference: referenceNode
        });
    }

    setProperty(target: DOMTarget, property: string | DomPropertyMap, value: DomPropertyValue, context: DOMContext = null): void {
        const element = resolveDOMElement(this, target, context);
        if (!element) return;

        if (!this.dependencies.isString(property)) {
            if (!this.dependencies.isPlainObject(property)) {
                throw new TypeError('setProperty properties map must be a plain object');
            }
            const properties: DomPropertyMap = Object.fromEntries(Object.entries(property));
            this.#queueUpdate(element, {
                type: 'properties',
                properties
            });
            return;
        }
        this.#queueUpdate(element, {
            type: 'property',
            property,
            value
        });
    }

    remove(target: DOMTarget, context: DOMContext = null): void {
        const element = resolveDOMElement(this, target, context);
        if (!element) return;

        if (element instanceof Element) {
            cleanupDOMListeners(this, element);
        }
        this.#queueUpdate(element, {
            type: 'remove'
        });
    }

    setVisibility(target: DOMTarget, visible: boolean, context: DOMContext = null): void {
        this.#enqueue(target, context, { type: 'visibility', visible });
    }

    flush(): void {
        flushDOMUpdates(this);
    }

    getMetrics(): PerformanceMetrics {
        return { ...this.performanceMetrics };
    }

    resetMetrics(): void {
        this.performanceMetrics = {
            totalUpdates: 0,
            batchedUpdates: 0,
            averageBatchSize: 0
        };
    }

    registerListener(element: Element, event: string, handler: EventListener): void {
        if (!element || !event || !handler) return;
        const existing = this.listenerRegistry.get(element);
        if (!this.dependencies.isNullOrUndefined(existing) && !this.dependencies.isArray(existing)) {
            throw new TypeError('Listener registry must contain arrays');
        }
        const listeners = existing ?? [];
        listeners.push({ event, handler });
        this.listenerRegistry.set(element, listeners);
    }

    destroy(): void {
        if (this.batchTimer) {
            const cancelAnimationFrame = this.dependencies.getCancelAnimationFrame();
            cancelAnimationFrame(this.batchTimer);
            this.batchTimer = null;
        }
        this.pendingUpdates.clear();
        this.listenerRegistry = new WeakMap();
    }

    setBatchingEnabled(enabled: boolean): void {
        this.batchingEnabled = Boolean(enabled);
    }

    #enqueue(target: DOMTarget, context: DOMContext, update: DOMUpdate): void {
        const element = resolveDOMElement(this, target, context);
        if (element) {
            this.#queueUpdate(element, update);
        }
    }

    #queueUpdate(element: Element | DocumentFragment, update: DOMUpdate): void {
        queueDOMUpdate(this, element, null, update);
    }
}

const createDomUpdateService = (dependencies: DomUpdateServiceDependencies): DOMUpdateService => new DOMUpdateService(dependencies);

export { DOMUpdateService, createDomUpdateService };
