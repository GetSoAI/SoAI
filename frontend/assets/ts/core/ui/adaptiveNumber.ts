/* SoAI - Shared UI adaptive number [frontend/assets/ts/core/ui/adaptiveNumber.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { securityApi, toTrustedUiHtml } from '@core/security/public.ts';
import { isHTMLElement } from '@core/typeGuards.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type AdaptiveNumberHost = PageDomOwnerHost;

const ADAPTIVE_NUMBER_SELECTOR = '.ui-adaptive-number';

const renderAdaptiveNumber = (fullValue: string, compactValue: string, className: string = 'ui-adaptive-number'): string => {
    const escapedFullText = securityApi.escapeHtml(fullValue);
    const escapedFullValue = securityApi.escapeAttribute(fullValue);
    const escapedCompactValue = securityApi.escapeAttribute(compactValue);
    const escapedClassName = securityApi.escapeAttribute(className);
    return `<span class="${escapedClassName}" data-full-value="${escapedFullValue}" data-compact-value="${escapedCompactValue}" data-tooltip="${escapedFullValue}">${escapedFullText}</span>`;
};

const isAdaptiveNumberOverflowing = (element: HTMLElement): boolean => {
    const parent = element.parentElement;
    if (!isHTMLElement(parent)) {
        return false;
    }
    return element.scrollWidth > element.clientWidth || parent.scrollWidth > parent.clientWidth;
};

const applyAdaptiveNumbers = (root: Element | Document): void => {
    const elements = dom.resolveAll(ADAPTIVE_NUMBER_SELECTOR, root).filter(isHTMLElement);
    for (const element of elements) {
        const fullValue = dom.getData(element, 'fullValue');
        if (fullValue !== null) {
            dom.setText(element, fullValue);
        }
    }
    dom.flush();
    for (const element of elements) {
        const fullValue = dom.getData(element, 'fullValue');
        const compactValue = dom.getData(element, 'compactValue');
        if (fullValue === null || compactValue === null || fullValue === compactValue) {
            continue;
        }
        if (isAdaptiveNumberOverflowing(element)) {
            dom.setText(element, compactValue);
        }
    }
    dom.flush();
};

const updateAdaptiveNumber = (host: AdaptiveNumberHost, element: HTMLElement, fullValue: string, compactValue: string, className: string = 'ui-adaptive-number'): void => {
    const html = renderAdaptiveNumber(fullValue, compactValue, className);
    const trustedHtml = toTrustedUiHtml(html);
    if (element.innerHTML !== html) {
        host.pageDom.updateHtml(element, trustedHtml);
    }
    host.pageDom.flush();
    applyAdaptiveNumbers(element);
};

const resolveAdaptiveNumberText = (cell: HTMLTableCellElement): string => {
    const element = dom.resolve(ADAPTIVE_NUMBER_SELECTOR, cell);
    if (isHTMLElement(element)) {
        return (dom.getData(element, 'fullValue') ?? element.textContent ?? '').trim();
    }
    return (cell.textContent ?? '').trim();
};

export { applyAdaptiveNumbers, renderAdaptiveNumber, resolveAdaptiveNumberText, updateAdaptiveNumber };
