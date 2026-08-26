/* SoAI - Frontend lifecycle DOM access ownership [frontend/assets/ts/core/lifecyclemodel/LifecycleDomAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom, getDomUpdateService, type DOMTarget, type DOMUpdateService } from '@core/dom/dom.ts';
import type { DomPropertyMap, DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { ReplaceContentOptions, UpdateHTMLOptions } from '@core/lifecyclemodel/types.ts';
import { isTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { isArray, isElementNode, isHTMLElement, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const normalizeDataAttributeName = (name: string): string => {
    let normalized = String(name).trim();
    if (!normalized) return '';
    normalized = normalized.startsWith('data-') ? normalized.slice(5) : normalized;
    normalized = normalized
        .replace(/[_\s]+/g, '-')
        .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
        .replace(/-+/g, '-')
        .replace(/^-+/, '')
        .toLowerCase();
    return normalized ? `data-${normalized}` : '';
};

class LifecycleDomAccess {
    #context: () => Element | Document | null;
    #identifier: () => string | undefined;
    #service: DOMUpdateService | null = null;
    domUpdate?: DOMUpdateService;

    constructor(context: () => Element | Document | null, identifier: () => string | undefined = () => undefined) {
        this.#context = context;
        this.#identifier = identifier;
    }

    resolveContext(context?: Element | Document | null): Element | Document | null {
        return context ?? this.#context();
    }

    resolve(selector: string | Element | Window | Document | null | undefined, context?: Element | Document | null): Element | Window | Document | null {
        if (!selector) return null;
        const documentTarget = dom.getDocument();
        const resolvedContext = context ?? documentTarget;
        if (isElementNode(selector)) return selector;
        if (selector === window) return window;
        if (selector === documentTarget) return documentTarget;
        return isString(selector) ? dom.resolve(selector, resolvedContext) : null;
    }

    resolveAll(selector: JsonValue | null | undefined, context?: Element | Document | null): Element[] {
        if (!selector) return [];
        const resolvedContext = context ?? dom.getDocument();
        if (isElementNode(selector)) return [selector];
        return isString(selector) ? dom.resolveAll(selector, resolvedContext) : [];
    }

    get(selector: string | Element, context?: Element | Document | null): Element | null {
        return isElementNode(selector) ? selector : dom.getUI(selector, this.resolveContext(context));
    }

    optional(selector: string | Element, context?: Element | Document | null): Element | null {
        return this.get(selector, context);
    }

    require(selector: string | Element, context?: Element | Document | null): Element {
        const element = this.get(selector, context);
        if (element) return element;
        throw new Error(`${this.#identifier() || 'module'}: required UI missing: ${selector}`);
    }

    optionalHTMLElement(selector: string | Element, context?: Element | Document | null): HTMLElement | null {
        const element = this.get(selector, context);
        if (!element) return null;
        if (isHTMLElement(element)) return element;
        throw new Error(`${this.#identifier() || 'module'}: optional UI must be an HTMLElement when present: ${selector}`);
    }

    requireHTMLElement(selector: string | Element, context?: Element | Document | null): HTMLElement {
        const element = this.require(selector, context);
        if (isHTMLElement(element)) return element;
        throw new Error(`${this.#identifier() || 'module'}: required UI must be an HTMLElement: ${selector}`);
    }

    query(selector: string | Element | string[], context?: Element | Document | null): Element[] {
        if (isElementNode(selector)) return [selector];
        const selectors = isArray(selector) ? selector : [selector];
        return selectors.flatMap((candidate) => dom.resolveAll(candidate, this.resolveContext(context)));
    }

    service(): DOMUpdateService | null {
        if (isObject(this.domUpdate)) return this.domUpdate;
        this.#service ??= getDomUpdateService();
        return this.#service;
    }

    reset(): void {
        this.#service = null;
    }

    updateText(target: DOMTarget, text: string, context?: Element | Document | null): void {
        this.service()?.setText(target, text, this.resolveContext(context));
    }

    updateHtml(target: DOMTarget, html: TrustedHtml | string, options: UpdateHTMLOptions = {}): void {
        const escape = typeof options.escape === 'boolean' ? options.escape : !isTrustedHtml(html);
        this.service()?.setHTML(target, html, { escape, context: this.resolveContext(options.context) });
    }

    updateAttribute(target: DOMTarget, attribute: string, value: string | null, context?: Element | Document | null): void {
        let normalizedValue: string | null = null;
        if (!isNullOrUndefined(value)) {
            if (!isString(value)) throw new Error(`updateAttribute requires a string value for ${attribute}`);
            normalizedValue = value;
        }
        this.service()?.setAttribute(target, attribute, normalizedValue, this.resolveContext(context));
    }

    updateStyle(target: DOMTarget, property: string, value: string | null, context?: Element | Document | null): void {
        this.service()?.setStyle(target, property, value, this.resolveContext(context));
    }

    updateStyles(target: DOMTarget, styles: Record<string, string | null>, context?: Element | Document | null): void {
        this.service()?.setStyle(target, styles, null, this.resolveContext(context));
    }

    addClass(target: DOMTarget, classes: string | string[], context?: Element | Document | null): void {
        this.service()?.addClass(target, classes, this.resolveContext(context));
    }

    removeClass(target: DOMTarget, classes: string | string[], context?: Element | Document | null): void {
        this.service()?.removeClass(target, classes, this.resolveContext(context));
    }

    toggleClass(target: DOMTarget, className: string, force?: boolean | null, context?: Element | Document | null): void {
        this.service()?.toggleClass(target, className, force ?? null, this.resolveContext(context));
    }

    updateProperty(target: DOMTarget, property: string, value: DomPropertyValue, context?: Element | Document | null): void {
        this.service()?.setProperty(target, property, value, this.resolveContext(context));
    }

    updateProperties(target: DOMTarget, properties: DomPropertyMap, context?: Element | Document | null): void {
        this.service()?.setProperty(target, properties, null, this.resolveContext(context));
    }

    setDataAttribute(target: DOMTarget, name: string, value: string | null, context?: Element | Document | null): void {
        const attribute = normalizeDataAttributeName(name);
        if (attribute) this.updateAttribute(target, attribute, value, context);
    }

    getDataAttribute(target: Element | null, name: string): string | null {
        if (!target || !isHTMLElement(target)) return null;
        const attribute = normalizeDataAttributeName(name);
        return attribute ? target.getAttribute(attribute) : null;
    }

    replaceContent(target: DOMTarget, content: string | TrustedHtml | DocumentFragment | HTMLElement, options: ReplaceContentOptions = {}): void {
        const escape = typeof options.escape === 'boolean' ? options.escape : typeof content === 'string' ? true : false;
        this.service()?.replaceContent(target, content, { escape, context: this.resolveContext(options.context) });
    }

    append(target: DOMTarget, children: Node | Node[], context?: Element | Document | null): void {
        this.service()?.appendChild(target, children, this.resolveContext(context));
    }

    insertBefore(target: DOMTarget, element: Node | Node[], reference: DOMTarget, context?: Element | Document | null): void {
        this.service()?.insertBefore(target, element, reference, this.resolveContext(context));
    }

    remove(target: DOMTarget, context?: Element | Document | null): void {
        this.service()?.remove(target, this.resolveContext(context));
    }

    setVisible(target: DOMTarget, visible: boolean, context?: Element | Document | null): void {
        this.service()?.setVisibility(target, visible, this.resolveContext(context));
    }

    flush(): void {
        this.service()?.flush();
    }
}

export { LifecycleDomAccess };
