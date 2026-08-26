/* SoAI - Routed page scoped DOM query and mutation ownership [frontend/assets/ts/core/routing/pages/basepagecore/PageDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom, getDomUpdateService, type DOMTarget, type DOMUpdateService } from '@core/dom/dom.ts';
import type { DomPropertyMap, DomPropertyValue } from '@core/dom/propertyValues.ts';
import { resolvePageUiElement, resolvePageUiElements } from '@core/routing/pages/basepagecore/selectors.ts';
import { isTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { isHTMLElement, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';

interface PageDomControls {
    getContext(): Element | null;
}

interface PageDomHtmlOptions {
    escape?: boolean;
    context?: Element | Document | null;
}

const normalizeDataAttributeName = (name: string): string => {
    let normalized = String(name || '').trim();
    if (!normalized) {
        return '';
    }
    normalized = normalized.startsWith('data-') ? normalized.slice(5) : normalized;
    normalized = normalized
        .replace(/[_\s]+/g, '-')
        .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
        .replace(/-+/g, '-')
        .replace(/^-+/, '')
        .toLowerCase();
    return normalized ? `data-${normalized}` : '';
};

class PageDom {
    readonly #controls: PageDomControls;
    readonly #classMutationHandlers = new Set<(target: DOMTarget, classes: string | string[], context?: Element | Document | null) => void>();
    #updates: DOMUpdateService | null = null;

    constructor(controls: PageDomControls) {
        this.#controls = controls;
    }

    getContext(): Element | null {
        return this.#controls.getContext();
    }

    resolveContext(context?: Element | Document | null): Element | Document | null {
        return context ?? this.getContext();
    }

    onClassMutation(handler: (target: DOMTarget, classes: string | string[], context?: Element | Document | null) => void): () => void {
        this.#classMutationHandlers.add(handler);
        return () => this.#classMutationHandlers.delete(handler);
    }

    get(selector: string | Element, context?: Element | Document | null): Element | null {
        return resolvePageUiElement(selector, context ?? this.getContext() ?? dom.getDocument());
    }

    optional(selector: string | Element, context?: Element | Document | null): Element | null {
        return this.get(selector, context);
    }

    require(selector: string | Element, context?: Element | Document | null): Element {
        const element = this.get(selector, context);
        if (!element) {
            throw new Error(`Required page UI is missing: ${String(selector)}`);
        }
        return element;
    }

    optionalHTMLElement(selector: string | Element, context?: Element | Document | null): HTMLElement | null {
        const element = this.get(selector, context);
        if (!element) {
            return null;
        }
        if (!isHTMLElement(element)) {
            throw new Error(`Optional page UI must be an HTMLElement: ${String(selector)}`);
        }
        return element;
    }

    requireHTMLElement(selector: string | Element, context?: Element | Document | null): HTMLElement {
        const element = this.require(selector, context);
        if (!isHTMLElement(element)) {
            throw new Error(`Required page UI must be an HTMLElement: ${String(selector)}`);
        }
        return element;
    }

    query(selector: string | Element | string[], context?: Element | Document | null): Element[] {
        return resolvePageUiElements(selector, context ?? this.getContext() ?? dom.getDocument());
    }

    updateText(target: DOMTarget, text: string, context?: Element | Document | null): void {
        this.#service().setText(target, text, this.resolveContext(context));
    }

    updateHtml(target: DOMTarget, html: TrustedHtml | string, options: PageDomHtmlOptions = {}): void {
        const escape = typeof options.escape === 'boolean' ? options.escape : !isTrustedHtml(html);
        this.#service().setHTML(target, html, { escape, context: this.resolveContext(options.context) });
    }

    updateAttribute(target: DOMTarget, attribute: string, value: string | null, context?: Element | Document | null): void {
        if (!isNullOrUndefined(value) && !isString(value)) {
            throw new Error(`updateAttribute requires a string value for ${attribute}`);
        }
        this.#service().setAttribute(target, attribute, value, this.resolveContext(context));
    }

    updateStyle(target: DOMTarget, property: string, value: string | null, context?: Element | Document | null): void {
        this.#service().setStyle(target, property, value, this.resolveContext(context));
    }

    updateStyles(target: DOMTarget, styles: Record<string, string | null>, context?: Element | Document | null): void {
        if (isObject(styles)) {
            this.#service().setStyle(target, styles, null, this.resolveContext(context));
        }
    }

    addClass(target: DOMTarget, classes: string | string[], context?: Element | Document | null): void {
        this.#service().addClass(target, classes, this.resolveContext(context));
        this.#emitClassMutation(target, classes, context);
    }

    removeClass(target: DOMTarget, classes: string | string[], context?: Element | Document | null): void {
        this.#service().removeClass(target, classes, this.resolveContext(context));
        this.#emitClassMutation(target, classes, context);
    }

    toggleClass(target: DOMTarget, className: string, force?: boolean | null, context?: Element | Document | null): void {
        this.#service().toggleClass(target, className, force ?? null, this.resolveContext(context));
        this.#emitClassMutation(target, className, context);
    }

    updateProperty(target: DOMTarget, property: string, value: DomPropertyValue, context?: Element | Document | null): void {
        this.#service().setProperty(target, property, value, this.resolveContext(context));
    }

    updateProperties(target: DOMTarget, properties: DomPropertyMap, context?: Element | Document | null): void {
        if (isObject(properties)) {
            this.#service().setProperty(target, properties, null, this.resolveContext(context));
        }
    }

    setDataAttribute(target: DOMTarget, name: string, value: string | null, context?: Element | Document | null): void {
        const attribute = normalizeDataAttributeName(name);
        if (attribute) {
            this.updateAttribute(target, attribute, value, context);
        }
    }

    getDataAttribute(target: Element | null, name: string): string | null {
        if (!isHTMLElement(target)) {
            return null;
        }
        const attribute = normalizeDataAttributeName(name);
        return attribute ? target.getAttribute(attribute) : null;
    }

    replaceContent(target: DOMTarget, content: string | TrustedHtml | DocumentFragment | HTMLElement, options: PageDomHtmlOptions = {}): void {
        const escape = typeof options.escape === 'boolean' ? options.escape : typeof content === 'string';
        this.#service().replaceContent(target, content, { escape, context: this.resolveContext(options.context) });
    }

    append(target: DOMTarget, children: Node | Node[], context?: Element | Document | null): void {
        this.#service().appendChild(target, children, this.resolveContext(context));
    }

    insertBefore(target: DOMTarget, children: Node | Node[], reference: DOMTarget, context?: Element | Document | null): void {
        this.#service().insertBefore(target, children, reference, this.resolveContext(context));
    }

    remove(target: DOMTarget, context?: Element | Document | null): void {
        this.#service().remove(target, this.resolveContext(context));
    }

    setVisible(target: DOMTarget, visible: boolean, context?: Element | Document | null): void {
        this.#service().setVisibility(target, visible, this.resolveContext(context));
    }

    flush(): void {
        this.#service().flush();
    }

    reset(): void {
        this.#updates = null;
    }

    #emitClassMutation(target: DOMTarget, classes: string | string[], context?: Element | Document | null): void {
        for (const handler of this.#classMutationHandlers) handler(target, classes, context);
    }

    #service(): DOMUpdateService {
        this.#updates ??= getDomUpdateService();
        return this.#updates;
    }
}

export { PageDom };
export type { PageDomControls };
export interface PageDomOwnerHost {
    pageDom: PageDom;
}
