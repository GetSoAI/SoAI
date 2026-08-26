/* SoAI - Shared DOM patching primitives [frontend/assets/ts/core/dom/patching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { applyTextContent } from '@core/dom/textContent.ts';
import { isHTMLElement } from '@core/typeGuards.ts';

const EMPTY_PRESERVED_ATTRIBUTE_NAMES = new Set<string>();

const resolveHTMLElement = (selector: string, container: Element): HTMLElement | null => {
    const node = dom.resolve(selector, container);
    return node && isHTMLElement(node) ? node : null;
};

const syncAttribute = (inputArguments: { target: HTMLElement; source: HTMLElement; name: string }): boolean => {
    return syncAttributeValue(inputArguments.target, inputArguments.name, inputArguments.source.getAttribute(inputArguments.name));
};

const syncAttributeValue = (target: HTMLElement, name: string, value: string | null): boolean => {
    const currentValue = target.getAttribute(name);
    if (value === null) {
        if (currentValue === null) {
            return false;
        }
        target.removeAttribute(name);
        return true;
    }
    if (currentValue === value) {
        return false;
    }
    target.setAttribute(name, value);
    return true;
};

const syncTextContent = (target: HTMLElement, value: string): boolean => {
    return applyTextContent(target, value);
};

const syncStyleProperty = (target: HTMLElement, property: string, value: string): boolean => {
    if (target.style.getPropertyValue(property) === value) {
        return false;
    }
    target.style.setProperty(property, value);
    return true;
};

const syncClass = (target: HTMLElement, source: HTMLElement): boolean => {
    const sourceClasses = source.classList;
    const targetClasses = target.classList;
    if (sourceClasses.length === 0) {
        if (targetClasses.length === 0) {
            return false;
        }
        const toRemove: string[] = [];
        for (const className of Array.from(targetClasses)) {
            toRemove.push(className);
        }
        if (toRemove.length === 0) {
            return false;
        }
        targetClasses.remove(...toRemove);
        return true;
    }

    let changed = false;
    for (const existingClass of Array.from(targetClasses)) {
        if (!sourceClasses.contains(existingClass)) {
            targetClasses.remove(existingClass);
            changed = true;
        }
    }
    for (const requiredClass of Array.from(sourceClasses)) {
        if (!targetClasses.contains(requiredClass)) {
            targetClasses.add(requiredClass);
            changed = true;
        }
    }
    return changed;
};

const syncAttributes = (inputArguments: { target: HTMLElement; source: HTMLElement; preservedAttributeNames?: ReadonlySet<string> }): boolean => {
    const preservedAttributeNames = inputArguments.preservedAttributeNames ?? EMPTY_PRESERVED_ATTRIBUTE_NAMES;
    let changed = false;
    const sourceAttributeNames = new Set<string>();
    for (const attribute of Array.from(inputArguments.source.attributes)) {
        if (attribute.name === 'class') {
            continue;
        }
        sourceAttributeNames.add(attribute.name);
        if (preservedAttributeNames.has(attribute.name)) {
            continue;
        }
        if (syncAttribute({ target: inputArguments.target, source: inputArguments.source, name: attribute.name })) {
            changed = true;
        }
    }
    for (const attribute of Array.from(inputArguments.target.attributes)) {
        if (attribute.name === 'class') {
            continue;
        }
        if (preservedAttributeNames.has(attribute.name) || sourceAttributeNames.has(attribute.name)) {
            continue;
        }
        inputArguments.target.removeAttribute(attribute.name);
        changed = true;
    }
    return changed;
};

const syncElementShell = (inputArguments: { target: HTMLElement; source: HTMLElement; preservedAttributeNames?: ReadonlySet<string> }): boolean => {
    let changed = syncClass(inputArguments.target, inputArguments.source);
    if (syncAttributes(inputArguments)) {
        changed = true;
    }
    return changed;
};

const haveEqualChildNodes = (target: Element, source: Element): boolean => {
    if (target.childNodes.length !== source.childNodes.length) {
        return false;
    }
    for (let index = 0; index < target.childNodes.length; index += 1) {
        if (!target.childNodes[index]?.isEqualNode(source.childNodes[index] ?? null)) {
            return false;
        }
    }
    return true;
};

const replaceChildrenIfChanged = (target: Element, source: Element): boolean => {
    if (haveEqualChildNodes(target, source)) {
        return false;
    }
    target.replaceChildren(...Array.from(source.childNodes).map((node) => node.cloneNode(true)));
    return true;
};

export { haveEqualChildNodes, replaceChildrenIfChanged, resolveHTMLElement, syncAttribute, syncAttributeValue, syncAttributes, syncClass, syncElementShell, syncStyleProperty, syncTextContent };
