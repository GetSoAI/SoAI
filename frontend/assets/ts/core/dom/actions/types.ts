/* SoAI - Shared DOM actions contracts [frontend/assets/ts/core/dom/actions/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDomCache } from '@core/dom/domCache.ts';
import type { DomPropertyMap, DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { TrustedHtml } from '@core/security/public.ts';

import type { DOMUpdateService } from '@core/dom/service.ts';
import type { DOMChildContent, DOMContext, DOMQueryRoot, DOMRuntimeCandidate, DOMTarget, ElementOptions, ReplaceContentOptions, SetHTMLOptions } from '@core/dom/types.ts';

interface DomResolverDependencies {
    getDomDocument: () => Document;
    domCache: ReturnType<typeof createDomCache>;
}

interface DomResolverApi {
    ensureArray: <T>(value: T | T[] | null | undefined) => T[];
    isElement: (value: DOMRuntimeCandidate) => value is Element | Document | Window;
    isDocument: (value: DOMRuntimeCandidate) => value is Document;
    isWindow: (value: DOMRuntimeCandidate) => value is Window;
    querySafe: (selector: string, context?: DOMContext) => Element | null;
    safeQueryAll: (selector: string, context?: DOMContext) => Element[];
    resolve: (target: DOMTarget, context?: DOMContext) => Element | null;
    resolveAll: (targets: DOMTarget | DOMTarget[], context?: DOMContext) => Element[];
    resolveContainer: (container: HTMLElement | string | null | undefined) => HTMLElement | null;
    matches: (element: DOMTarget, selector: string) => boolean;
    closest: (element: DOMTarget, selector: string) => Element | null;
    apply: (targets: DOMTarget | DOMTarget[], callback: ((element: Element, index: number) => void) | undefined, context?: DOMContext) => Element[];
}

interface DomResolver {
    domCache: ReturnType<typeof createDomCache>;
    normalizeContext: (context: DOMContext) => DOMQueryRoot;
    querySafe: (selector: string, context?: DOMContext) => Element | null;
    safeQueryAll: (selector: string, context?: DOMContext) => Element[];
    getUI: (selector: DOMTarget, context?: DOMContext) => Element | null;
    resolve: (target: DOMTarget, context?: DOMContext) => Element | null;
    resolveAll: (targets: DOMTarget | DOMTarget[], context?: DOMContext) => Element[];
    resolveContainer: (container: HTMLElement | string | null | undefined) => HTMLElement | null;
    matches: (element: DOMTarget, selector: string) => boolean;
    closest: (element: DOMTarget, selector: string) => Element | null;
    apply: (targets: DOMTarget | DOMTarget[], callback: ((element: Element, index: number) => void) | undefined, context?: DOMContext) => Element[];
    domResolverApi: DomResolverApi;
}

interface DomActionsDependencies {
    domUpdateService: DOMUpdateService;
    getDynamicStyleValue: (element: Element, property: string) => string;
}

interface DomApi {
    getDocument(): Document;
    getDocumentElement(): HTMLElement;
    getBody(): HTMLElement;
    getHead(): HTMLHeadElement;
    getActiveElement(): Element | null;
    createFragment(html?: TrustedHtml): DocumentFragment;
    createFragmentFromNodes(children?: DOMChildContent): DocumentFragment;
    create(tagName: keyof HTMLElementTagNameMap | string, options?: ElementOptions): HTMLElement;
    createSvgElement(tagName: string, options?: ElementOptions): SVGElement;
    createText(content?: string): Text;
    createComment(content?: string): Comment;
    resolve(target: DOMTarget, context?: DOMContext): Element | null;
    querySafe(selector: string, context?: DOMContext): Element | null;
    resolveAll(targets: DOMTarget | DOMTarget[], context?: DOMContext): Element[];
    isElement(value: DOMRuntimeCandidate): value is Element | Document | Window;
    getStyleValue(target: DOMTarget, property: string, context?: DOMContext): string;
    setHTML(target: DOMTarget, html: TrustedHtml | string, options?: SetHTMLOptions): void;
    setText(target: DOMTarget, text: string | number | boolean | null | undefined, context?: DOMContext): void;
    setAttribute(target: DOMTarget, attribute: string, value: string | null, context?: DOMContext): void;
    removeAttribute(target: DOMTarget, attribute: string, context?: DOMContext): void;
    setData(target: DOMTarget, name: string, value: string | null, context?: DOMContext): void;
    getData(target: DOMTarget, name: string): string | null;
    setStyle(target: DOMTarget, property: string, value: string | null, context?: DOMContext): void;
    setStyles(target: DOMTarget, styles: Record<string, string | null>, context?: DOMContext): void;
    addClass(target: DOMTarget, classes: string | string[], context?: DOMContext): void;
    removeClass(target: DOMTarget, classes: string | string[], context?: DOMContext): void;
    toggleClass(target: DOMTarget, className: string, force: boolean | null, context?: DOMContext): void;
    hasClass(target: DOMTarget, className: string): boolean;
    getClasses(target: DOMTarget): string[];
    setProperty(target: DOMTarget, property: string, value: DomPropertyValue, context?: DOMContext): void;
    setProperties(target: DOMTarget, properties: DomPropertyMap, context?: DOMContext): void;
    replaceContent(target: DOMTarget, content: string | DocumentFragment | HTMLElement, options?: ReplaceContentOptions): void;
    appendChild(target: DOMTarget, children: DOMChildContent, context?: DOMContext): void;
    insertBefore(target: DOMTarget, children: DOMChildContent, reference: DOMTarget, context?: DOMContext): void;
    remove(target: DOMTarget, context?: DOMContext): void;
    setVisibility(target: DOMTarget, visible: boolean, context?: DOMContext): void;
    show(target: DOMTarget, context?: DOMContext): void;
    hide(target: DOMTarget, context?: DOMContext): void;
    replaceElement(target: DOMTarget, newContent: TrustedHtml | Node, context?: DOMContext): Element | null;
    querySelector(parent: DOMTarget, selector: string): Element | null;
    querySelectorAll(parent: DOMTarget, selector: string): Element[];
    getUI(selector: DOMTarget, context?: DOMContext): Element | null;
    flush(): void;
}

interface DomActionsBundle {
    dom: DomApi;
}

export type { DomActionsBundle, DomActionsDependencies, DomApi, DomResolver, DomResolverDependencies, DomResolverApi };
