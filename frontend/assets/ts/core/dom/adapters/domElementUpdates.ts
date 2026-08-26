/* SoAI - Frontend DOM element update adapters [frontend/assets/ts/core/dom/adapters/domElementUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { isDocumentFragment } from '@core/dom/domEnvironment.ts';

import type { DOMContext, DOMTarget, DOMUpdate } from '@core/dom/types.ts';
import type { DOMUpdateServiceRuntime } from '@core/dom/internalContracts.ts';
import { createHtmlFragment } from '@core/dom/html.ts';
import { applyTextContent } from '@core/dom/textContent.ts';
import { applyClassList, applyDataset, applyKnownProperty, applyStyleValue, appendNodes } from '@core/dom/adapters/updatePrimitives.ts';
import { ensureError } from '@core/errors/coerce.ts';

const applyDOMUpdate = (runtime: DOMUpdateServiceRuntime, element: Element | DocumentFragment, updates: DOMUpdate[]): void => {
    if (isDocumentFragment(element)) {
        for (const update of updates) {
            try {
                if (update.type === 'appendChild') {
                    appendNodes(runtime, element, update.children);
                    continue;
                }
                if (update.type === 'insertBefore') {
                    appendNodes(runtime, element, update.children, update.reference);
                    continue;
                }
                if (update.type === 'text') {
                    applyTextContent(element, update.value);
                    continue;
                }
                runtime.dependencies.errorHandler.warn('DOMUpdateService', `Skipping update type ${update.type} for DocumentFragment`);
            } catch (error) {
                const detail = ensureError(error);
                runtime.dependencies.errorHandler.warn('DOMUpdateService', `Failed to apply update type: ${update.type}`, detail);
            }
        }
        return;
    }

    for (const update of updates) {
        try {
            switch (update.type) {
                case 'text':
                    applyTextContent(element, update.value);
                    break;
                case 'html': {
                    const htmlElement = element instanceof HTMLElement ? element : null;
                    const scrollEntries = htmlElement ? runtime.dependencies.captureScrollState(htmlElement) : [];
                    const fragment = createHtmlFragment({ documentRef: runtime.dependencies.getDomDocument(), html: update.value, context: element });
                    if (typeof element.replaceChildren === 'function') {
                        element.replaceChildren(fragment);
                    } else {
                        element.textContent = '';
                        element.appendChild(fragment);
                    }
                    if (htmlElement) {
                        runtime.dependencies.restoreScrollState(scrollEntries);
                    }
                    break;
                }
                case 'attribute': {
                    const { attribute, value } = update;
                    if (attribute === 'id') {
                        const previousId = element.getAttribute('id');
                        const canApplyToken = (token: string | null): token is string => runtime.dependencies.isString(token) && Boolean(runtime.dependencies.toTrimmedString(token)) && !/\s/.test(token);
                        if (runtime.dependencies.isNullOrUndefined(value)) {
                            if (canApplyToken(previousId)) {
                                element.classList.remove(previousId);
                            }
                            element.removeAttribute(attribute);
                        } else {
                            const token = String(value);
                            if (canApplyToken(previousId) && previousId !== token) {
                                element.classList.remove(previousId);
                            }
                            element.setAttribute(attribute, token);
                            if (canApplyToken(token)) {
                                element.classList.add(token);
                            }
                        }
                    } else if (runtime.dependencies.isNullOrUndefined(value)) {
                        element.removeAttribute(attribute);
                    } else {
                        element.setAttribute(attribute, String(value));
                    }
                    break;
                }
                case 'style':
                    applyStyleValue(runtime, element, update.property, update.value);
                    break;
                case 'styles': {
                    if (!runtime.dependencies.isPlainObject(update.styles)) {
                        throw new TypeError('update.styles must be an object');
                    }
                    for (const [property, value] of Object.entries(update.styles)) {
                        applyStyleValue(runtime, element, property, value);
                    }
                    break;
                }
                case 'addClass':
                    applyClassList(runtime, element, update.classes, 'add');
                    break;
                case 'removeClass':
                    applyClassList(runtime, element, update.classes, 'remove');
                    break;
                case 'toggleClass':
                    element.classList.toggle(update.className, runtime.dependencies.isNullOrUndefined(update.force) ? !element.classList.contains(update.className) : Boolean(update.force));
                    break;
                case 'replaceContent': {
                    const htmlElement = element instanceof HTMLElement ? element : null;
                    const scrollEntries = htmlElement ? runtime.dependencies.captureScrollState(htmlElement) : [];
                    if (isDocumentFragment(update.content) || runtime.dependencies.isHTMLElement(update.content)) {
                        element.textContent = '';
                        element.appendChild(update.content);
                    }
                    if (htmlElement) {
                        runtime.dependencies.restoreScrollState(scrollEntries);
                    }
                    break;
                }
                case 'appendChild':
                    appendNodes(runtime, element, update.children);
                    break;
                case 'insertBefore':
                    appendNodes(runtime, element, update.children, update.reference);
                    break;
                case 'property':
                    if (update.property === 'dataset') {
                        applyDataset(runtime, element, update.value);
                    } else if (!applyKnownProperty({ element, property: update.property, value: update.value, toString: runtime.dependencies.toString })) {
                        throw new Error(`Unsupported DOM property update: ${update.property}`);
                    }
                    break;
                case 'properties':
                    if (!runtime.dependencies.isPlainObject(update.properties)) {
                        throw new TypeError('update.properties must be an object');
                    }
                    for (const [property, value] of Object.entries(update.properties)) {
                        if (property === 'dataset') {
                            applyDataset(runtime, element, value);
                            continue;
                        }
                        if (applyKnownProperty({ element, property, value, toString: runtime.dependencies.toString })) {
                            continue;
                        }
                        if (runtime.dependencies.isNullOrUndefined(value) || value === false) {
                            element.removeAttribute(property);
                        } else if (value === true) {
                            element.setAttribute(property, '');
                        } else {
                            element.setAttribute(property, runtime.dependencies.toString(value));
                        }
                    }
                    break;
                case 'remove':
                    element.remove();
                    break;
                case 'visibility':
                    element.classList.toggle(CSS_CLASSES.HIDDEN, !update.visible);
                    element.setAttribute('aria-hidden', update.visible ? 'false' : 'true');
                    break;
            }
        } catch (error) {
            const detail = ensureError(error);
            runtime.dependencies.errorHandler.warn('DOMUpdateService', `Failed to apply update type: ${update.type}`, detail);
        }
    }
};

const resolveDOMElement = (runtime: DOMUpdateServiceRuntime, target: DOMTarget, context: DOMContext = null): Element | DocumentFragment | null => {
    if (!target) return null;
    if (isDocumentFragment(target)) return target;
    if (runtime.dependencies.isElementNode(target)) {
        return target;
    }
    if (runtime.dependencies.isString(target)) {
        return runtime.dependencies.resolve(target, context);
    }
    return null;
};

export { applyDOMUpdate, resolveDOMElement };
