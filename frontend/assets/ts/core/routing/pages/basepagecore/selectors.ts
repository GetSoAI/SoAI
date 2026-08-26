/* SoAI - Shared routing selectors [frontend/assets/ts/core/routing/pages/basepagecore/selectors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { normalizeSelectorForResolve, normalizeSelectorList } from '@core/routing/pages/pageDom.ts';
import { isArray, isElementNode, isString } from '@core/typeGuards.ts';

const resolvePageUiElement = (selector: string | Element, context: Document | Element): Element | null => {
    const normalized = normalizeSelectorForResolve(selector);
    if (isElementNode(normalized)) {
        return normalized;
    }
    if (!isString(normalized)) {
        return null;
    }
    return dom.resolve(normalized, context);
};

const resolvePageUiElements = (selector: string | Element | string[], context: Document | Element): Element[] => {
    const normalized = normalizeSelectorList(selector);
    const targets: Array<string | Element> = [];
    if (isArray(normalized)) {
        for (const entry of normalized) {
            if (isString(entry) || isElementNode(entry)) {
                targets.push(entry);
            }
        }
    } else if (isString(normalized) || isElementNode(normalized)) {
        targets.push(normalized);
    }
    if (!targets.length) {
        return [];
    }
    return dom.resolveAll(targets, context) || [];
};

export { resolvePageUiElement, resolvePageUiElements };
