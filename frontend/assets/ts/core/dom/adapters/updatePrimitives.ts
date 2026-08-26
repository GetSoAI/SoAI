/* SoAI - Shared DOM update primitives [frontend/assets/ts/core/dom/adapters/updatePrimitives.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DOMUpdateServiceRuntime } from '@core/dom/internalContracts.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { setSelectSelectedIndexAndSyncDefault, setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';

const DATASET_KEY_PATTERN = /^[a-z][a-zA-Z0-9]*$/;

const toDataAttributeName = (key: string): string => {
    if (!DATASET_KEY_PATTERN.test(key)) {
        throw new Error(`Dataset keys must be lowerCamelCase: ${key}`);
    }
    return `data-${key.replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`)}`;
};

const applyKnownProperty = (inputArguments: { element: Element; property: string; value: DomPropertyValue | null | undefined; toString: (value: DomPropertyValue | null | undefined) => string }): boolean => {
    const { element, property, value, toString } = inputArguments;

    switch (property) {
        case 'checked': {
            if (!(element instanceof HTMLInputElement)) {
                return false;
            }
            if (typeof value !== 'boolean') {
                throw new TypeError('checked property update requires a boolean value');
            }
            element.checked = value;
            return true;
        }
        case 'selected': {
            if (!(element instanceof HTMLOptionElement)) {
                return false;
            }
            if (typeof value !== 'boolean') {
                throw new TypeError('selected property update requires a boolean value');
            }
            element.selected = value;
            element.defaultSelected = value;
            if (value) {
                element.setAttribute('selected', '');
            } else {
                element.removeAttribute('selected');
            }
            return true;
        }
        case 'value': {
            const next = toString(value);
            if (element instanceof HTMLInputElement) {
                element.value = next;
                return true;
            }
            if (element instanceof HTMLTextAreaElement) {
                element.value = next;
                return true;
            }
            if (element instanceof HTMLSelectElement) {
                setSelectValueAndSyncDefault(element, next);
                return true;
            }
            element.setAttribute('value', next);
            return true;
        }
        case 'disabled': {
            const next = Boolean(value);
            if (element instanceof HTMLButtonElement) {
                element.disabled = next;
                return true;
            }
            if (element instanceof HTMLInputElement) {
                element.disabled = next;
                return true;
            }
            if (element instanceof HTMLSelectElement) {
                element.disabled = next;
                return true;
            }
            if (element instanceof HTMLTextAreaElement) {
                element.disabled = next;
                return true;
            }
            element.toggleAttribute('disabled', next);
            return true;
        }
        case 'placeholder': {
            const next = toString(value);
            if (element instanceof HTMLInputElement) {
                element.placeholder = next;
                return true;
            }
            if (element instanceof HTMLTextAreaElement) {
                element.placeholder = next;
                return true;
            }
            element.setAttribute('placeholder', next);
            return true;
        }
        case 'className': {
            const next = toString(value);
            element.classList.value = next;
            return true;
        }
        case 'src': {
            const next = toString(value);
            if (element instanceof HTMLImageElement) {
                element.src = next;
                return true;
            }
            element.setAttribute('src', next);
            return true;
        }
        case 'alt': {
            const next = toString(value);
            if (element instanceof HTMLImageElement) {
                element.alt = next;
                return true;
            }
            element.setAttribute('alt', next);
            return true;
        }
        case 'scrollTop': {
            if (!(element instanceof HTMLElement)) {
                return false;
            }
            if (typeof value !== 'number' || !Number.isFinite(value)) {
                throw new TypeError('scrollTop property update requires a finite number value');
            }
            element.scrollTop = value;
            return true;
        }
        case 'scrollLeft': {
            if (!(element instanceof HTMLElement)) {
                return false;
            }
            if (typeof value !== 'number' || !Number.isFinite(value)) {
                throw new TypeError('scrollLeft property update requires a finite number value');
            }
            element.scrollLeft = value;
            return true;
        }
        case 'tabIndex': {
            if (!(element instanceof HTMLElement)) {
                return false;
            }
            if (typeof value !== 'number' || !Number.isFinite(value)) {
                throw new TypeError('tabIndex property update requires a finite number value');
            }
            element.tabIndex = value;
            return true;
        }
        case 'selectedIndex': {
            if (!(element instanceof HTMLSelectElement)) {
                return false;
            }
            if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isInteger(value)) {
                throw new TypeError('selectedIndex property update requires an integer value');
            }
            setSelectSelectedIndexAndSyncDefault(element, value);
            return true;
        }
    }

    return false;
};

const appendNodes = (runtime: DOMUpdateServiceRuntime, element: Node, nodes: Node[], reference: Node | null = null): void => {
    const nodesToAppend = runtime.dependencies.ensureArray(nodes);
    if (!nodesToAppend.length) return;

    const doc = runtime.dependencies.getDomDocument();
    const fragment = doc.createDocumentFragment();

    for (const node of nodesToAppend) {
        if (runtime.dependencies.isNode(node)) {
            fragment.appendChild(node);
        }
    }
    if (!fragment.childNodes.length) return;

    if (runtime.dependencies.isNode(reference) && element.contains(reference)) {
        element.insertBefore(fragment, reference);
        return;
    }
    element.appendChild(fragment);
};

const applyStyleValue = (runtime: DOMUpdateServiceRuntime, element: Element, property: string, value: string | null): void => {
    if (!element || !property) return;
    if (element instanceof HTMLElement || element instanceof SVGElement) {
        runtime.dependencies.applyDynamicStyle(element, property, value);
    }
};

const applyClassList = (runtime: DOMUpdateServiceRuntime, element: Element, classes: string[], method: 'add' | 'remove'): void => {
    if (!runtime.dependencies.isElementNode(element) || !classes.length) return;

    if (method === 'add') {
        element.classList.add(...classes);
        return;
    }

    element.classList.remove(...classes);
};

const applyDataset = (runtime: DOMUpdateServiceRuntime, element: Element, datasetValue: DomPropertyValue): void => {
    if (!(element instanceof HTMLElement)) return;

    if (runtime.dependencies.isNullOrUndefined(datasetValue)) {
        const attributes = Array.from(element.attributes);
        for (const attribute of attributes) {
            if (attribute.name.startsWith('data-')) {
                element.removeAttribute(attribute.name);
            }
        }
        return;
    }

    if (!runtime.dependencies.isPlainObject(datasetValue)) {
        throw new TypeError('dataset value must be a plain object');
    }

    for (const [key, value] of Object.entries(datasetValue)) {
        const attributeName = toDataAttributeName(key);
        if (runtime.dependencies.isNullOrUndefined(value)) {
            element.removeAttribute(attributeName);
        } else {
            element.setAttribute(attributeName, runtime.dependencies.toString(value));
        }
    }
};

export { applyClassList, applyDataset, applyKnownProperty, applyStyleValue, appendNodes };
