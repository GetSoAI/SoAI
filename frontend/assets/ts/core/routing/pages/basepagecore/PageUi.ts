/* SoAI - Routed page element creation, loading state, canvas, and checkerboard ownership [frontend/assets/ts/core/routing/pages/basepagecore/PageUi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { dom, type ElementOptions } from '@core/dom/dom.ts';
import { resolveCanvasRenderPixelRatio } from '@core/layout/canvasGeometry.ts';
import { i18n } from '@core/i18n/index.ts';
import type { loadingState } from '@core/loadingState.ts';
import { err, request, requestFunctionValue } from '@core/routing/pages/basepagecore/actions.ts';
import { setBasePageUIValue } from '@core/routing/pages/basepagecore/dom.ts';
import { isCustomValidityTarget } from '@core/routing/pages/basepagecore/guards.ts';
import { createPageSectionElement } from '@core/routing/pages/basepagecore/sectionFactory.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import { requireCheckerboardService } from '@core/routing/pages/pageDom.ts';
import type { CanvasPrepareResult, CreateSectionOptions, SetBusyOptions, SetUIValueOptions } from '@core/routing/pages/pagetypes/public.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { isArray, isElementNode, isNode, isObject, isString } from '@core/typeGuards.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';

interface PageUiDependencies {
    loadingState: typeof loadingState;
    layout: PageLayout;
    pageDom: PageDom;
}

class PageUi {
    readonly #dependencies: PageUiDependencies;
    readonly #canvasSignatures = new WeakMap<HTMLCanvasElement, string>();
    #checkerboardContainer: Element | null = null;
    #checkerboardSelector: string | null = null;

    constructor(dependencies: PageUiDependencies) {
        this.#dependencies = dependencies;
    }

    resolveElement(target: string | Element, optional = false): Element | null {
        const element = this.#dependencies.pageDom.get(target);
        if (!element && !optional) throw err(`UI element unavailable: ${isString(target) ? target : target.tagName.toLowerCase()}`);
        return element;
    }

    getElement(selector: string | Element, context?: Element): Element | null {
        return this.#dependencies.pageDom.get(selector, context);
    }

    setValue(target: string | Element, value: string | null | undefined, options: SetUIValueOptions = {}): void {
        setBasePageUIValue(
            {
                getElement: (selector, context) => this.getElement(selector, context),
                updateAttribute: (element, attribute, nextValue, context) => this.#dependencies.pageDom.updateAttribute(element, attribute, nextValue, context),
                updateText: (element, text, context) => this.#dependencies.pageDom.updateText(element, text, context),
                setDataAttribute: (element, name, nextValue, context) => this.#dependencies.pageDom.setDataAttribute(element, name, nextValue, context),
                toggleVisibility: (selector, visible) => this.toggleVisibility(selector, visible)
            },
            target,
            value ?? null,
            options
        );
    }

    createElement<K extends keyof HTMLElementTagNameMap>(tag: K, attributes?: ElementOptions | null, child?: string | Node): HTMLElementTagNameMap[K];
    createElement(tag: string, attributes?: ElementOptions | null, child?: string | Node): HTMLElement;
    createElement(tag: string, attributes: ElementOptions | null = {}, child: string | Node = ''): HTMLElement {
        const element = dom.create(tag, { ...(isObject(attributes) ? attributes : {}), includeIdClass: false });
        if (child) this.#dependencies.pageDom.append(element, isNode(child) ? child : dom.createText(String(child)));
        this.#dependencies.pageDom.flush();
        return element;
    }

    appendTo(target: string | Element, content: (string | Node)[] | string | Node): void {
        const element = this.#dependencies.pageDom.get(target);
        if (!element) return;
        this.#dependencies.pageDom.append(element, dom.createFragmentFromNodes(isArray(content) ? content : [content]));
        this.#dependencies.pageDom.flush();
    }

    prepareCanvas(id: string): CanvasPrepareResult {
        const element = this.#dependencies.pageDom.get(id);
        if (!(element instanceof HTMLCanvasElement)) throw err('Canvas element missing');
        const context = element.getContext('2d');
        if (!context) throw err('Canvas context null');
        const rectangle = measureLayoutBox(element);
        const ratio = resolveCanvasRenderPixelRatio(element);
        const width = Math.max(0, rectangle.width);
        const height = Math.max(0, rectangle.height);
        const signature = `${width}:${height}:${ratio}`;
        if (this.#canvasSignatures.get(element) !== signature) {
            element.width = width * ratio;
            element.height = height * ratio;
            this.#dependencies.pageDom.updateStyles(element, { width: `${width}px`, height: `${height}px` });
            this.#canvasSignatures.set(element, signature);
            this.#dependencies.pageDom.flush();
        }
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        return { canvas: element, context: context, width, height };
    }

    toggleVisibility(selector: string | Element[], visible: boolean): void {
        const elements = isString(selector) ? this.#dependencies.pageDom.query(selector) : [selector].flat();
        elements.forEach((element) => {
            if (element) this.toggleHidden(element, !visible);
        });
    }

    toggleHidden(elementOrSelector: Element | string, hidden: boolean): void {
        const element = this.#dependencies.pageDom.get(elementOrSelector);
        if (!element) return;
        this.#dependencies.pageDom.toggleClass(element, CSS_CLASSES.HIDDEN, hidden);
        this.#dependencies.pageDom.updateAttribute(element, 'aria-hidden', hidden ? 'true' : null);
        this.#dependencies.pageDom.flush();
    }

    setBusy(target: Element | string | Element[], busy: boolean, { className = 'busy', disable = true, ...options }: SetBusyOptions = {}): void {
        const elements = isString(target) ? this.#dependencies.pageDom.query(target) : [target].flat();
        elements.forEach((element) => {
            if (!element) return;
            this.#dependencies.pageDom.toggleClass(element, className, busy);
            if ('disabled' in element && disable) this.#dependencies.pageDom.updateProperty(element, 'disabled', busy);
            setAriaBusy(element, busy);
            if (isCustomValidityTarget(element) && options.customValidity) element.setCustomValidity(busy ? options.customValidity.busy : '');
        });
        this.#dependencies.pageDom.flush();
    }

    setLoadingState(elementOrSelector: Element | string, loading: boolean, text: string = i18n.t('common.loading')): void {
        const element = this.#dependencies.pageDom.get(elementOrSelector);
        if (!isElementNode(element)) throw err('Element missing');
        requestFunctionValue(request(this.#dependencies.loadingState, 'LS'), 'setElementState', 'LS')(element, loading, text, { withSpinner: false, strict: true });
        this.#dependencies.pageDom.flush();
    }

    createLoadingState(target: string | Element): { stop: () => void } {
        const element = this.#dependencies.pageDom.get(target);
        const text = i18n.t('common.loading');
        if (!element) throw err('Element missing');
        this.setLoadingState(element, true, text);
        return { stop: () => this.setLoadingState(element, false, text) };
    }

    createSection(id: string, { title = i18n.t('common.section.defaultTitle'), subtitle = '', controls = EMPTY_UI_HTML, className = 'section', position = null, showSubtitle = true, loadingText }: CreateSectionOptions = {}): HTMLElement {
        return createPageSectionElement(id, { title, subtitle, controls, className, position, showSubtitle, loadingText }, { createElement: (tag, attributes) => this.createElement(tag, attributes), applyGridPosition: (element, gridPosition) => this.#dependencies.layout.applyGridPosition(element, gridPosition), updateHTML: (element, html, options) => this.#dependencies.pageDom.updateHtml(element, html, options) });
    }

    enableCheckerboard(containerOrSelector: Element | string, id?: string, absoluteIndexOffset: number = 0): void {
        const element = this.#dependencies.pageDom.get(containerOrSelector);
        if (!element) throw err('Container missing');
        const checkerboard = requireCheckerboardService();
        if (this.#checkerboardContainer !== null && this.#checkerboardContainer !== element) {
            checkerboard.disconnect(checkerboard.getContainerId(this.#checkerboardContainer));
        }
        this.#checkerboardContainer = element;
        this.#checkerboardSelector = id ?? null;
        checkerboard.applyCheckerboard(element, id, absoluteIndexOffset);
    }

    updateCheckerboard(absoluteIndexOffset?: number): void {
        if (!this.#checkerboardContainer) return;
        if (absoluteIndexOffset === undefined) {
            requireCheckerboardService().updateCheckerboard(this.#checkerboardContainer, this.#checkerboardSelector ?? undefined);
            return;
        }
        requireCheckerboardService().updateCheckerboard(this.#checkerboardContainer, this.#checkerboardSelector ?? undefined, absoluteIndexOffset);
    }

    get checkerboardContainer(): Element | null {
        return this.#checkerboardContainer;
    }
}

export { PageUi };
export interface PageUiOwnerHost {
    pageElements: PageUi;
}
export type { PageUiDependencies };
