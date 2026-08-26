/* SoAI - Shared DOM actions service [frontend/assets/ts/core/dom/actions/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDomDocument, SVG_NAMESPACE, isElement } from '@core/dom/domEnvironment.ts';
import type { DomPropertyMap, DomPropertyValue } from '@core/dom/propertyValues.ts';
import { isHTMLElement, isPlainObject, isString, hasOwn } from '@core/typeGuards.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { TrustedHtml } from '@core/security/public.ts';

import { applyNodesToFragment, querySelectorAllFromTarget, querySelectorFromTarget, replaceResolvedElement } from '@core/dom/actions/effects.ts';
import { applyElementOptions, createElement } from '@core/dom/actions/guards.ts';
import { buildFragmentFromNodes, normalizeChildren, normalizeDataName } from '@core/dom/actions/mappers.ts';
import type { DomActionsBundle, DomActionsDependencies, DomResolver } from '@core/dom/actions/types.ts';
import type { DOMChildContent, DOMContext, DOMRuntimeCandidate, DOMTarget, ElementOptions, ElementOptionValue, ReplaceContentOptions, SetHTMLOptions } from '@core/dom/types.ts';
import { createHtmlFragment } from '@core/dom/html.ts';

const createDomActions = (dependencies: DomActionsDependencies, resolver: DomResolver): DomActionsBundle => {
    const { domUpdateService, getDynamicStyleValue } = dependencies;
    const { normalizeContext, resolve, resolveAll, querySafe, getUI } = resolver;

    const dom: DomActionsBundle['dom'] = {
        getDocument(): Document {
            const documentRef = getDomDocument();
            if (!documentRef) throw new Error('Document is unavailable');
            return documentRef;
        },

        getDocumentElement(): HTMLElement {
            const documentRef = dom.getDocument();
            const element = documentRef.documentElement;
            if (!isHTMLElement(element)) throw new Error('Document element is unavailable');
            return element;
        },

        getBody(): HTMLElement {
            const documentRef = dom.getDocument();
            const body = documentRef.body;
            if (!isHTMLElement(body)) throw new Error('Document body is unavailable');
            return body;
        },

        getHead(): HTMLHeadElement {
            const documentRef = dom.getDocument();
            const head = documentRef.head;
            if (!head) throw new Error('Document head is unavailable');
            return head;
        },

        getActiveElement(): Element | null {
            const documentRef = dom.getDocument();
            return documentRef.activeElement ?? null;
        },

        createFragment(html?: TrustedHtml): DocumentFragment {
            if (!html || !toTrimmedString(html.html)) {
                return getDomDocument().createDocumentFragment();
            }
            const documentRef = getDomDocument();
            return createHtmlFragment({ documentRef, html: html.html, context: documentRef });
        },

        createFragmentFromNodes(children?: DOMChildContent): DocumentFragment {
            return buildFragmentFromNodes(children);
        },

        create(tagName: keyof HTMLElementTagNameMap | string, options: ElementOptions = {}): HTMLElement {
            const element = createElement(tagName, getDomDocument);
            applyElementOptions(element, options, dom);
            return element;
        },

        createSvgElement(tagName: string, options: ElementOptions = {}): SVGElement {
            if (!isString(tagName) || !toTrimmedString(tagName)) {
                throw new Error('createSvgElement requires a valid tagName');
            }
            const element = getDomDocument().createElementNS(SVG_NAMESPACE, toTrimmedString(tagName));
            if (!(typeof SVGElement === 'function' && element instanceof SVGElement)) {
                throw new Error('createSvgElement must create an SVGElement');
            }
            const props: Record<string, ElementOptionValue> = isPlainObject(options) ? { ...options } : {};
            if (!hasOwn(props, 'includeIdClass')) {
                props['includeIdClass'] = false;
            }
            applyElementOptions(element, props, dom, { preferAttributes: true });
            return element;
        },

        createText(content = ''): Text {
            const documentRef = dom.getDocument();
            return documentRef.createTextNode(content ?? '');
        },

        createComment(content = ''): Comment {
            const documentRef = dom.getDocument();
            return documentRef.createComment(content ?? '');
        },

        resolve(target: DOMTarget, context?: DOMContext): Element | null {
            return resolve(target, context);
        },

        querySafe(selector: string, context?: DOMContext): Element | null {
            return querySafe(selector, context ?? null);
        },

        resolveAll(targets: DOMTarget | DOMTarget[], context?: DOMContext): Element[] {
            return resolveAll(targets, context ?? null);
        },

        isElement(value: DOMRuntimeCandidate): value is Element | Document | Window {
            return isElement(value);
        },

        getStyleValue(target: DOMTarget, property: string, context: DOMContext = null): string {
            const element = resolve(target, context);
            if (!element || !property) return '';
            return getDynamicStyleValue(element, property);
        },

        setHTML(target: DOMTarget, html: TrustedHtml | string, options: SetHTMLOptions = {}): void {
            const { escape = true, context = null } = options;
            domUpdateService.setHTML(target, html, { escape, context: normalizeContext(context) });
        },

        setText(target: DOMTarget, text: string | number | boolean | null | undefined, context: DOMContext = null): void {
            domUpdateService.setText(target, text, normalizeContext(context));
        },

        setAttribute(target: DOMTarget, attribute: string, value: string | null, context: DOMContext = null): void {
            domUpdateService.setAttribute(target, attribute, value, normalizeContext(context));
        },

        removeAttribute(target: DOMTarget, attribute: string, context: DOMContext = null): void {
            domUpdateService.setAttribute(target, attribute, null, normalizeContext(context));
        },

        setData(target: DOMTarget, name: string, value: string | null, context: DOMContext = null): void {
            const normalized = normalizeDataName(name);
            if (!normalized) return;
            const attribute = `data-${normalized}`;
            dom.setAttribute(target, attribute, value, context);
        },

        getData(target: DOMTarget, name: string): string | null {
            const element = resolve(target);
            if (!element) return null;
            if (!element.getAttribute) return null;

            const attribute = normalizeDataName(name);
            if (!attribute) return null;
            return element.getAttribute(`data-${attribute}`);
        },

        setStyle(target: DOMTarget, property: string, value: string | null, context: DOMContext = null): void {
            domUpdateService.setStyle(target, property, value, normalizeContext(context));
        },

        setStyles(target: DOMTarget, styles: Record<string, string | null>, context: DOMContext = null): void {
            if (!styles || !isPlainObject(styles)) return;
            domUpdateService.setStyle(target, styles, null, normalizeContext(context));
        },

        addClass(target: DOMTarget, classes: string | string[], context: DOMContext = null): void {
            domUpdateService.addClass(target, classes, normalizeContext(context));
        },

        removeClass(target: DOMTarget, classes: string | string[], context: DOMContext = null): void {
            domUpdateService.removeClass(target, classes, normalizeContext(context));
        },

        toggleClass(target: DOMTarget, className: string, force: boolean | null = null, context: DOMContext = null): void {
            domUpdateService.toggleClass(target, className, force, normalizeContext(context));
        },

        hasClass(target: DOMTarget, className: string): boolean {
            const element = resolve(target);
            if (!element || !className) return false;
            return element.classList.contains(className);
        },

        getClasses(target: DOMTarget): string[] {
            const element = resolve(target);
            if (!element) return [];
            return Array.from(element.classList);
        },

        setProperty(target: DOMTarget, property: string, value: DomPropertyValue, context: DOMContext = null): void {
            domUpdateService.setProperty(target, property, value, normalizeContext(context));
        },

        setProperties(target: DOMTarget, properties: DomPropertyMap, context: DOMContext = null): void {
            if (!properties || !isPlainObject(properties)) return;
            domUpdateService.setProperty(target, properties, null, normalizeContext(context));
        },

        replaceContent(target: DOMTarget, content: string | DocumentFragment | HTMLElement, options: ReplaceContentOptions = {}): void {
            const { escape = true, context = null } = options;
            domUpdateService.replaceContent(target, content, { escape, context: normalizeContext(context) });
        },

        appendChild(target: DOMTarget, children: DOMChildContent, context: DOMContext = null): void {
            const nodes = normalizeChildren(children);
            if (applyNodesToFragment(target, nodes)) return;
            domUpdateService.appendChild(target, nodes, normalizeContext(context));
        },

        insertBefore(target: DOMTarget, children: DOMChildContent, reference: DOMTarget = null, context: DOMContext = null): void {
            const nodes = normalizeChildren(children);
            if (applyNodesToFragment(target, nodes, reference)) return;
            domUpdateService.insertBefore(target, nodes, reference, normalizeContext(context));
        },

        remove(target: DOMTarget, context: DOMContext = null): void {
            domUpdateService.remove(target, normalizeContext(context));
        },

        setVisibility(target: DOMTarget, visible: boolean, context: DOMContext = null): void {
            domUpdateService.setVisibility(target, Boolean(visible), normalizeContext(context));
        },

        show(target: DOMTarget, context: DOMContext = null): void {
            domUpdateService.setVisibility(target, true, normalizeContext(context));
        },

        hide(target: DOMTarget, context: DOMContext = null): void {
            domUpdateService.setVisibility(target, false, normalizeContext(context));
        },

        replaceElement(target: DOMTarget, newContent: TrustedHtml | Node, context: DOMContext = null): Element | null {
            return replaceResolvedElement(resolve, dom.createFragment, target, newContent, context);
        },

        querySelector(parent: DOMTarget, selector: string): Element | null {
            return querySelectorFromTarget(resolve, parent, selector);
        },

        querySelectorAll(parent: DOMTarget, selector: string): Element[] {
            return querySelectorAllFromTarget(resolve, resolveAll, parent, selector);
        },

        getUI(selector: DOMTarget, context?: DOMContext): Element | null {
            return getUI(selector, context);
        },

        flush(): void {
            domUpdateService.flush();
        }
    };

    return { dom };
};

export { createDomActions };
