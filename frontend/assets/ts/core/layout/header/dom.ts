/* SoAI - Shared layout header DOM contracts [frontend/assets/ts/core/layout/header/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getWindow } from '@core/environment/public.ts';
import { isString } from '@core/typeGuards.ts';
import { HEADER_SELECTORS, type HeaderDomKey } from '@core/layout/header/state.ts';

const optionalChildHTMLElement = (parent: Element, selector: string): HTMLElement | SVGElement | null => {
    const element = dom.resolve(selector, parent);
    if (element === null) return null;
    if (element instanceof HTMLElement) return element;
    if (typeof SVGElement === 'function' && element instanceof SVGElement) return element;
    throw new Error(`Header expected HTMLElement or SVGElement for selector: ${selector}`);
};

const optionalChildElement = (parent: Element, selector: string): Element | null => dom.resolve(selector, parent);

const optionalDocumentHTMLElement = (selector: string): HTMLElement | null => {
    const doc = getWindow().document;
    const element = dom.resolve(selector, doc);
    if (element === null) return null;
    if (element instanceof HTMLElement) return element;
    throw new Error(`Header expected HTMLElement for selector: ${selector}`);
};

const optionalHeaderDom = (key: HeaderDomKey): HTMLElement | null => {
    const selector = HEADER_SELECTORS[key];
    if (!isString(selector) || !selector.trim()) throw new Error(`Header selector missing for key '${key}'`);
    return optionalDocumentHTMLElement(selector);
};

const requireHeaderDom = (key: HeaderDomKey): HTMLElement => {
    const resolved = optionalHeaderDom(key);
    if (!resolved) throw new Error(`Header missing required element '${key}'`);
    return resolved;
};

export { optionalHeaderDom, requireHeaderDom, optionalChildHTMLElement, optionalChildElement, optionalDocumentHTMLElement };
