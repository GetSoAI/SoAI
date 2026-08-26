/* SoAI - Shared typed DOM resolver helpers [frontend/assets/ts/core/dom/typedElementResolver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { narrowButton, narrowHTMLElement, narrowInput, narrowSelect, narrowTextarea, optionalAnchor, optionalButton, optionalHTMLElement, optionalImage, optionalInput, optionalSelect, optionalTextarea } from '@core/dom/narrowElement.ts';
import type { DOMQueryRoot } from '@core/dom/types.ts';

interface RequiredElementHost {
    requireElement: (selector: string, context?: Element) => Element;
}

interface OptionalElementHost {
    optionalElement: (selector: string, context?: Element) => Element | null;
}

const requireElementFromHost = (host: RequiredElementHost, selector: string, context?: Element): Element => (context ? host.requireElement(selector, context) : host.requireElement(selector));

const optionalElementFromHost = (host: OptionalElementHost, selector: string, context?: Element): Element | null => (context ? host.optionalElement(selector, context) : host.optionalElement(selector));

const requireResolvedHTMLElement = (host: RequiredElementHost, selector: string, label: string, context?: Element): HTMLElement => narrowHTMLElement(requireElementFromHost(host, selector, context), label);

const requireResolvedButton = (host: RequiredElementHost, selector: string, label: string, context?: Element): HTMLButtonElement => narrowButton(requireElementFromHost(host, selector, context), label);

const requireResolvedInput = (host: RequiredElementHost, selector: string, label: string, context?: Element): HTMLInputElement => narrowInput(requireElementFromHost(host, selector, context), label);

const requireResolvedSelect = (host: RequiredElementHost, selector: string, label: string, context?: Element): HTMLSelectElement => narrowSelect(requireElementFromHost(host, selector, context), label);

const requireResolvedTextarea = (host: RequiredElementHost, selector: string, label: string, context?: Element): HTMLTextAreaElement => narrowTextarea(requireElementFromHost(host, selector, context), label);

const requireResolvedCheckbox = (host: RequiredElementHost, selector: string, label: string, context?: Element): HTMLInputElement => {
    const input = requireResolvedInput(host, selector, label, context);
    if (input.type !== 'checkbox') {
        throw new TypeError(`${label} must be a checkbox input`);
    }
    return input;
};

const optionalResolvedHTMLElement = (host: OptionalElementHost, selector: string, label: string, context?: Element): HTMLElement | null => optionalHTMLElement(optionalElementFromHost(host, selector, context), label);

const optionalResolvedButton = (host: OptionalElementHost, selector: string, label: string, context?: Element): HTMLButtonElement | null => optionalButton(optionalElementFromHost(host, selector, context), label);

const optionalResolvedInput = (host: OptionalElementHost, selector: string, label: string, context?: Element): HTMLInputElement | null => optionalInput(optionalElementFromHost(host, selector, context), label);

const optionalResolvedSelect = (host: OptionalElementHost, selector: string, label: string, context?: Element): HTMLSelectElement | null => optionalSelect(optionalElementFromHost(host, selector, context), label);

const optionalResolvedTextarea = (host: OptionalElementHost, selector: string, label: string, context?: Element): HTMLTextAreaElement | null => optionalTextarea(optionalElementFromHost(host, selector, context), label);

const optionalResolvedAnchor = (host: OptionalElementHost, selector: string, label: string, context?: Element): HTMLAnchorElement | null => optionalAnchor(optionalElementFromHost(host, selector, context), label);

const optionalResolvedImage = (host: OptionalElementHost, selector: string, label: string, context?: Element): HTMLImageElement | null => optionalImage(optionalElementFromHost(host, selector, context), label);

const optionalRootHTMLElement = (root: DOMQueryRoot, selector: string, label: string): HTMLElement | null => optionalHTMLElement(dom.resolve(selector, root), label);

const optionalRootButton = (root: DOMQueryRoot, selector: string, label: string): HTMLButtonElement | null => optionalButton(dom.resolve(selector, root), label);

const optionalRootInput = (root: DOMQueryRoot, selector: string, label: string): HTMLInputElement | null => optionalInput(dom.resolve(selector, root), label);

const requireRootHTMLElement = (root: DOMQueryRoot, selector: string, label: string): HTMLElement => {
    const element = dom.resolve(selector, root);
    if (!element) {
        throw new Error(`${label} is required for selector: ${selector}`);
    }
    return narrowHTMLElement(element, label);
};

const requireRootButton = (root: DOMQueryRoot, selector: string, label: string): HTMLButtonElement => {
    const element = dom.resolve(selector, root);
    if (!element) {
        throw new Error(`${label} is required for selector: ${selector}`);
    }
    return narrowButton(element, label);
};

const requireRootInput = (root: DOMQueryRoot, selector: string, label: string): HTMLInputElement => {
    const element = dom.resolve(selector, root);
    if (!element) {
        throw new Error(`${label} is required for selector: ${selector}`);
    }
    return narrowInput(element, label);
};

const resolveButtonList = (selector: string, root: DOMQueryRoot, label: string): HTMLButtonElement[] => {
    const buttons: HTMLButtonElement[] = [];
    dom.resolveAll(selector, root).forEach((element) => {
        buttons.push(narrowButton(element, label));
    });
    return buttons;
};

const resolveHTMLElementList = (selector: string, root: DOMQueryRoot, label: string): HTMLElement[] => {
    const elements: HTMLElement[] = [];
    dom.resolveAll(selector, root).forEach((element) => {
        elements.push(narrowHTMLElement(element, label));
    });
    return elements;
};

const resolveInputList = (selector: string, root: DOMQueryRoot, label: string): HTMLInputElement[] => {
    const elements: HTMLInputElement[] = [];
    dom.resolveAll(selector, root).forEach((element) => {
        elements.push(narrowInput(element, label));
    });
    return elements;
};

const resolveTextareaList = (selector: string, root: DOMQueryRoot, label: string): HTMLTextAreaElement[] => {
    const elements: HTMLTextAreaElement[] = [];
    dom.resolveAll(selector, root).forEach((element) => {
        elements.push(narrowTextarea(element, label));
    });
    return elements;
};

export { optionalResolvedAnchor, optionalResolvedButton, optionalResolvedHTMLElement, optionalResolvedImage, optionalResolvedInput, optionalResolvedSelect, optionalResolvedTextarea, optionalRootButton, optionalRootHTMLElement, optionalRootInput, requireElementFromHost, requireResolvedButton, requireResolvedCheckbox, requireResolvedHTMLElement, requireResolvedInput, requireResolvedSelect, requireResolvedTextarea, requireRootButton, requireRootHTMLElement, requireRootInput, resolveButtonList, resolveHTMLElementList, resolveInputList, resolveTextareaList };
