/* SoAI - Shared frontend DOM narrow element [frontend/assets/ts/core/dom/narrowElement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const narrowButton = (element: Element, label: string): HTMLButtonElement => {
    if (!(element instanceof HTMLButtonElement)) {
        throw new TypeError(`${label} must be an HTMLButtonElement`);
    }
    return element;
};

const narrowInput = (element: Element, label: string): HTMLInputElement => {
    if (!(element instanceof HTMLInputElement)) {
        throw new TypeError(`${label} must be an HTMLInputElement`);
    }
    return element;
};

const narrowSelect = (element: Element, label: string): HTMLSelectElement => {
    if (!(element instanceof HTMLSelectElement)) {
        throw new TypeError(`${label} must be an HTMLSelectElement`);
    }
    return element;
};

const narrowTextarea = (element: Element, label: string): HTMLTextAreaElement => {
    if (!(element instanceof HTMLTextAreaElement)) {
        throw new TypeError(`${label} must be an HTMLTextAreaElement`);
    }
    return element;
};

const narrowTable = (element: Element, label: string): HTMLTableElement => {
    if (!(element instanceof HTMLTableElement)) {
        throw new TypeError(`${label} must be an HTMLTableElement`);
    }
    return element;
};

const narrowTableSection = (element: Element, label: string): HTMLTableSectionElement => {
    if (!(element instanceof HTMLTableSectionElement)) {
        throw new TypeError(`${label} must be an HTMLTableSectionElement`);
    }
    return element;
};

const narrowForm = (element: Element, label: string): HTMLFormElement => {
    if (!(element instanceof HTMLFormElement)) {
        throw new TypeError(`${label} must be an HTMLFormElement`);
    }
    return element;
};

const narrowImage = (element: Element, label: string): HTMLImageElement => {
    if (!(element instanceof HTMLImageElement)) {
        throw new TypeError(`${label} must be an HTMLImageElement`);
    }
    return element;
};

const narrowAnchor = (element: Element, label: string): HTMLAnchorElement => {
    if (!(element instanceof HTMLAnchorElement)) {
        throw new TypeError(`${label} must be an HTMLAnchorElement`);
    }
    return element;
};

const narrowHTMLElement = (element: Element, label: string): HTMLElement => {
    if (!(element instanceof HTMLElement)) {
        throw new TypeError(`${label} must be an HTMLElement`);
    }
    return element;
};

const optionalHTMLElement = (element: Element | null, label: string): HTMLElement | null => {
    if (!element) {
        return null;
    }
    return narrowHTMLElement(element, label);
};

const optionalButton = (element: Element | null, label: string): HTMLButtonElement | null => {
    if (!element) {
        return null;
    }
    return narrowButton(element, label);
};

const optionalInput = (element: Element | null, label: string): HTMLInputElement | null => {
    if (!element) {
        return null;
    }
    return narrowInput(element, label);
};

const optionalSelect = (element: Element | null, label: string): HTMLSelectElement | null => {
    if (!element) {
        return null;
    }
    return narrowSelect(element, label);
};

const optionalTextarea = (element: Element | null, label: string): HTMLTextAreaElement | null => {
    if (!element) {
        return null;
    }
    return narrowTextarea(element, label);
};

const optionalImage = (element: Element | null, label: string): HTMLImageElement | null => {
    if (!element) {
        return null;
    }
    return narrowImage(element, label);
};

const optionalAnchor = (element: Element | null, label: string): HTMLAnchorElement | null => {
    if (!element) {
        return null;
    }
    return narrowAnchor(element, label);
};

export { narrowAnchor, narrowButton, narrowForm, narrowHTMLElement, narrowImage, narrowInput, narrowSelect, narrowTable, narrowTableSection, narrowTextarea, optionalAnchor, optionalButton, optionalHTMLElement, optionalImage, optionalInput, optionalSelect, optionalTextarea };
