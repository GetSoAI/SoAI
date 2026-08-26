/* SoAI - Shared frontend DOM contracts [frontend/assets/ts/core/dom/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CheckerboardService, createCheckerboardService } from '@core/dom/checkerboardService.ts';
import { createDomResolver } from '@core/dom/actions/adapters.ts';
import { createDomActions } from '@core/dom/actions/service.ts';
import { createDomCache } from '@core/dom/domCache.ts';
import { getDomDocument, getDomWindow, initializeDomEnvironment } from '@core/dom/domEnvironment.ts';
import type { DomPropertyMap, DomPropertyValue } from '@core/dom/propertyValues.ts';
import { DomObserver, observeMutationsUntil, type ObserveMutationsOptions } from '@core/dom/domObserver.ts';
import { createDomUpdateService, DOMUpdateService } from '@core/dom/service.ts';
import type { DOMChildContent, DOMContext, DOMQueryRoot, DOMRuntimeCandidate, DOMTarget, DOMUpdate, ElementOptions, PerformanceMetrics, ReplaceContentOptions, ScrollStateEntry, SetHTMLOptions } from '@core/dom/types.ts';
import { narrowAnchor, narrowButton, narrowForm, narrowHTMLElement, narrowImage, narrowInput, narrowSelect, narrowTable, narrowTableSection, narrowTextarea, optionalAnchor, optionalButton, optionalHTMLElement, optionalImage, optionalInput, optionalSelect, optionalTextarea } from '@core/dom/narrowElement.ts';
import { createUIElementServiceFactory, UIElementService, type GetElementOptions } from '@core/dom/uiElementService.ts';
import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureArray, toString, toTrimmedString } from '@core/normalize.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { securityApi, type TrustedHtml } from '@core/security/public.ts';
import { applyDynamicStyle, captureScrollState, getDynamicStyleValue, restoreScrollState } from '@core/dom/state.ts';
import { isArray, isHTMLElement, isElementNode, isNode, isNullOrUndefined, isPlainObject, isString } from '@core/typeGuards.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';

type DomRuntime = {
    readonly domCache: ReturnType<typeof createDomCache>;
    readonly domResolver: ReturnType<typeof createDomResolver>;
    readonly domUpdateService: DOMUpdateService;
    readonly dom: ReturnType<typeof createDomActions>['dom'];
    readonly createUIElementService: ReturnType<typeof createUIElementServiceFactory>;
    readonly checkerboardService: CheckerboardService;
    readonly uiElementServiceModule: { readonly create: (ownerId: string) => UIElementService };
};

let runtime: DomRuntime | null = null;

const ensureDomRuntime = (): DomRuntime => {
    if (runtime) {
        return runtime;
    }

    const domCacheValue = createDomCache(getDomDocument);
    const domResolverValue = createDomResolver({
        getDomDocument,
        domCache: domCacheValue
    });

    const domUpdateServiceValue = createDomUpdateService({
        security: securityApi,
        errorHandler,
        ensureArray,
        toTrimmedString,
        toString,
        isPlainObject,
        isNullOrUndefined,
        isString,
        isArray,
        isElementNode,
        isNode,
        isHTMLElement,
        getDomDocument,
        getRequestAnimationFrame,
        getCancelAnimationFrame,
        captureScrollState,
        restoreScrollState,
        applyDynamicStyle: (element, property, value) => applyDynamicStyle(element, property, value),
        resolve: domResolverValue.resolve
    });

    const { dom } = createDomActions({ domUpdateService: domUpdateServiceValue, getDynamicStyleValue }, domResolverValue);

    const createUIElementServiceValue = createUIElementServiceFactory({
        getDomDocument,
        resolve: domResolverValue.resolve,
        resolveAll: domResolverValue.resolveAll
    });

    const checkerboardServiceValue = createCheckerboardService({
        createResourceTracker: (): ResourceTracker => new ResourceTracker(),
        getDomWindow,
        generateSecureId,
        dom: {
            addClass: (element, classes) => dom.addClass(element, classes),
            removeClass: (element, classes) => dom.removeClass(element, classes),
            getData: (element, name) => dom.getData(element, name),
            setData: (element, name, value) => dom.setData(element, name, value)
        }
    });

    const uiElementServiceModuleValue = Object.freeze({
        create: (ownerId: string): UIElementService => createUIElementServiceValue(ownerId)
    });

    runtime = {
        domCache: domCacheValue,
        domResolver: domResolverValue,
        domUpdateService: domUpdateServiceValue,
        dom,
        createUIElementService: createUIElementServiceValue,
        checkerboardService: checkerboardServiceValue,
        uiElementServiceModule: uiElementServiceModuleValue
    };
    return runtime;
};

const domCache = {
    get: (selector: string, context?: DOMContext): Element | null => ensureDomRuntime().domCache.get(selector, context),
    getAll: (selector: string, context?: DOMContext): Element[] => ensureDomRuntime().domCache.getAll(selector, context),
    clear: (): void => ensureDomRuntime().domCache.clear(),
    invalidate: (selector: string): void => ensureDomRuntime().domCache.invalidate(selector)
};

const getDomUpdateService = (): DOMUpdateService => ensureDomRuntime().domUpdateService;

const dom = {
    getDocument: (): Document => ensureDomRuntime().dom.getDocument(),
    getDocumentElement: (): HTMLElement => ensureDomRuntime().dom.getDocumentElement(),
    getBody: (): HTMLElement => ensureDomRuntime().dom.getBody(),
    getHead: (): HTMLHeadElement => ensureDomRuntime().dom.getHead(),
    getActiveElement: (): Element | null => ensureDomRuntime().dom.getActiveElement(),
    createFragment: (html?: TrustedHtml): DocumentFragment => ensureDomRuntime().dom.createFragment(html),
    createFragmentFromNodes: (children?: DOMChildContent): DocumentFragment => ensureDomRuntime().dom.createFragmentFromNodes(children),
    create: (tagName: keyof HTMLElementTagNameMap | string, options?: ElementOptions): HTMLElement => ensureDomRuntime().dom.create(tagName, options),
    createSvgElement: (tagName: string, options?: ElementOptions): SVGElement => ensureDomRuntime().dom.createSvgElement(tagName, options),
    createText: (content?: string): Text => ensureDomRuntime().dom.createText(content),
    createComment: (content?: string): Comment => ensureDomRuntime().dom.createComment(content),
    resolve: (target: DOMTarget, context?: DOMContext): Element | null => ensureDomRuntime().dom.resolve(target, context),
    querySafe: (selector: string, context?: DOMContext): Element | null => ensureDomRuntime().dom.querySafe(selector, context),
    resolveAll: (targets: DOMTarget | DOMTarget[], context?: DOMContext): Element[] => ensureDomRuntime().dom.resolveAll(targets, context),
    isElement: (value: DOMRuntimeCandidate): value is Element | Document | Window => ensureDomRuntime().dom.isElement(value),
    getStyleValue: (target: DOMTarget, property: string, context?: DOMContext): string => ensureDomRuntime().dom.getStyleValue(target, property, context),
    setHTML: (target: DOMTarget, html: TrustedHtml | string, options?: SetHTMLOptions): void => ensureDomRuntime().dom.setHTML(target, html, options),
    setText: (target: DOMTarget, text: string | number | boolean | null | undefined, context?: DOMContext): void => ensureDomRuntime().dom.setText(target, text, context),
    setAttribute: (target: DOMTarget, attribute: string, value: string | null, context?: DOMContext): void => ensureDomRuntime().dom.setAttribute(target, attribute, value, context),
    removeAttribute: (target: DOMTarget, attribute: string, context?: DOMContext): void => ensureDomRuntime().dom.removeAttribute(target, attribute, context),
    setData: (target: DOMTarget, name: string, value: string | null, context?: DOMContext): void => ensureDomRuntime().dom.setData(target, name, value, context),
    getData: (target: DOMTarget, name: string): string | null => ensureDomRuntime().dom.getData(target, name),
    setStyle: (target: DOMTarget, property: string, value: string | null, context?: DOMContext): void => ensureDomRuntime().dom.setStyle(target, property, value, context),
    setStyles: (target: DOMTarget, styles: Record<string, string | null>, context?: DOMContext): void => ensureDomRuntime().dom.setStyles(target, styles, context),
    addClass: (target: DOMTarget, classes: string | string[], context?: DOMContext): void => ensureDomRuntime().dom.addClass(target, classes, context),
    removeClass: (target: DOMTarget, classes: string | string[], context?: DOMContext): void => ensureDomRuntime().dom.removeClass(target, classes, context),
    toggleClass: (target: DOMTarget, className: string, force: boolean | null, context?: DOMContext): void => ensureDomRuntime().dom.toggleClass(target, className, force, context),
    hasClass: (target: DOMTarget, className: string): boolean => ensureDomRuntime().dom.hasClass(target, className),
    getClasses: (target: DOMTarget): string[] => ensureDomRuntime().dom.getClasses(target),
    setProperty: (target: DOMTarget, property: string, value: DomPropertyValue, context?: DOMContext): void => ensureDomRuntime().dom.setProperty(target, property, value, context),
    setProperties: (target: DOMTarget, properties: DomPropertyMap, context?: DOMContext): void => ensureDomRuntime().dom.setProperties(target, properties, context),
    replaceContent: (target: DOMTarget, content: string | DocumentFragment | HTMLElement, options?: ReplaceContentOptions): void => ensureDomRuntime().dom.replaceContent(target, content, options),
    appendChild: (target: DOMTarget, children: DOMChildContent, context?: DOMContext): void => ensureDomRuntime().dom.appendChild(target, children, context),
    insertBefore: (target: DOMTarget, children: DOMChildContent, reference: DOMTarget, context?: DOMContext): void => ensureDomRuntime().dom.insertBefore(target, children, reference, context),
    remove: (target: DOMTarget, context?: DOMContext): void => ensureDomRuntime().dom.remove(target, context),
    setVisibility: (target: DOMTarget, visible: boolean, context?: DOMContext): void => ensureDomRuntime().dom.setVisibility(target, visible, context),
    show: (target: DOMTarget, context?: DOMContext): void => ensureDomRuntime().dom.show(target, context),
    hide: (target: DOMTarget, context?: DOMContext): void => ensureDomRuntime().dom.hide(target, context),
    replaceElement: (target: DOMTarget, newContent: TrustedHtml | Node, context?: DOMContext): Element | null => ensureDomRuntime().dom.replaceElement(target, newContent, context),
    querySelector: (parent: DOMTarget, selector: string): Element | null => ensureDomRuntime().dom.querySelector(parent, selector),
    querySelectorAll: (parent: DOMTarget, selector: string): Element[] => ensureDomRuntime().dom.querySelectorAll(parent, selector),
    getUI: (selector: DOMTarget, context?: DOMContext): Element | null => ensureDomRuntime().dom.getUI(selector, context),
    flush: (): void => ensureDomRuntime().dom.flush()
};

const checkerboardService = {
    applyCheckerboard: (container: Element, itemSelector: string, absoluteIndexOffset: number = 0): void => ensureDomRuntime().checkerboardService.applyCheckerboard(container, itemSelector, absoluteIndexOffset),
    updateCheckerboard: (container: Element, itemSelector: string, absoluteIndexOffset?: number): void => ensureDomRuntime().checkerboardService.updateCheckerboard(container, itemSelector, absoluteIndexOffset),
    groupItemsIntoRows: (items: Element[], containerRect: DOMRect): Element[][] => ensureDomRuntime().checkerboardService.groupItemsIntoRows(items, containerRect),
    handleGlobalResize: (): void => ensureDomRuntime().checkerboardService.handleGlobalResize(),
    disconnect: (containerId: string): void => ensureDomRuntime().checkerboardService.disconnect(containerId),
    disconnectAll: (): void => ensureDomRuntime().checkerboardService.disconnectAll(),
    getContainerId: (container: Element): string => ensureDomRuntime().checkerboardService.getContainerId(container)
};

const createUIElementService = (ownerId: string): UIElementService => ensureDomRuntime().createUIElementService(ownerId);

const uiElementServiceModule = Object.freeze({
    create: (ownerId: string): UIElementService => ensureDomRuntime().uiElementServiceModule.create(ownerId)
});

const querySafe = (selector: string, context?: DOMContext): Element | null => ensureDomRuntime().domResolver.querySafe(selector, context);
const querySafeAll = (selector: string, context?: DOMContext): Element[] => ensureDomRuntime().domResolver.safeQueryAll(selector, context);
const resolve = (target: DOMTarget, context?: DOMContext): Element | null => ensureDomRuntime().domResolver.resolve(target, context);
const resolveAll = (targets: DOMTarget | DOMTarget[], context?: DOMContext): Element[] => ensureDomRuntime().domResolver.resolveAll(targets, context);
const resolveContainer = (container: HTMLElement | string | null | undefined): HTMLElement | null => ensureDomRuntime().domResolver.resolveContainer(container);
const matches = (element: DOMTarget, selector: string): boolean => ensureDomRuntime().domResolver.matches(element, selector);
const closest = (element: DOMTarget, selector: string): Element | null => ensureDomRuntime().domResolver.closest(element, selector);
const apply = (targets: DOMTarget | DOMTarget[], callback: ((element: Element, index: number) => void) | undefined, context?: DOMContext): Element[] => ensureDomRuntime().domResolver.apply(targets, callback, context);
const getUI = (selector: DOMTarget, context?: DOMContext): Element | null => ensureDomRuntime().domResolver.getUI(selector, context);
const normalizeContext = (context: DOMContext): DOMQueryRoot => ensureDomRuntime().domResolver.normalizeContext(context);
const domResolverApi = {
    ensureArray: <T>(value: T | T[] | null | undefined): T[] => ensureDomRuntime().domResolver.domResolverApi.ensureArray(value),
    isElement: (value: DOMRuntimeCandidate): value is Element | Document | Window => ensureDomRuntime().domResolver.domResolverApi.isElement(value),
    isDocument: (value: DOMRuntimeCandidate): value is Document => ensureDomRuntime().domResolver.domResolverApi.isDocument(value),
    isWindow: (value: DOMRuntimeCandidate): value is Window => ensureDomRuntime().domResolver.domResolverApi.isWindow(value),
    querySafe: (selector: string, context?: DOMContext): Element | null => ensureDomRuntime().domResolver.domResolverApi.querySafe(selector, context),
    safeQueryAll: (selector: string, context?: DOMContext): Element[] => ensureDomRuntime().domResolver.domResolverApi.safeQueryAll(selector, context),
    resolve: (target: DOMTarget, context?: DOMContext): Element | null => ensureDomRuntime().domResolver.domResolverApi.resolve(target, context),
    resolveAll: (targets: DOMTarget | DOMTarget[], context?: DOMContext): Element[] => ensureDomRuntime().domResolver.domResolverApi.resolveAll(targets, context),
    resolveContainer: (container: HTMLElement | string | null | undefined): HTMLElement | null => ensureDomRuntime().domResolver.domResolverApi.resolveContainer(container),
    matches: (element: DOMTarget, selector: string): boolean => ensureDomRuntime().domResolver.domResolverApi.matches(element, selector),
    closest: (element: DOMTarget, selector: string): Element | null => ensureDomRuntime().domResolver.domResolverApi.closest(element, selector),
    apply: (targets: DOMTarget | DOMTarget[], callback: ((element: Element, index: number) => void) | undefined, context?: DOMContext): Element[] => ensureDomRuntime().domResolver.domResolverApi.apply(targets, callback, context)
};

export { CheckerboardService, DomObserver, DOMUpdateService, UIElementService, apply, captureScrollState, checkerboardService, closest, createUIElementService, dom, domCache, domResolverApi, ensureArray, getDomUpdateService, getUI, initializeDomEnvironment, matches, narrowAnchor, narrowButton, narrowForm, narrowHTMLElement, narrowImage, narrowInput, narrowSelect, narrowTable, narrowTableSection, narrowTextarea, normalizeContext, observeMutationsUntil, optionalAnchor, optionalButton, optionalHTMLElement, optionalImage, optionalInput, optionalSelect, optionalTextarea, querySafe, querySafeAll, restoreScrollState, resolve, resolveAll, resolveContainer, uiElementServiceModule };

export type { DOMChildContent, DOMRuntimeCandidate, DOMTarget, DOMContext, DOMQueryRoot, DOMUpdate, SetHTMLOptions, ReplaceContentOptions, GetElementOptions, ObserveMutationsOptions, ScrollStateEntry, PerformanceMetrics, ElementOptions };
