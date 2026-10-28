/* SoAI - Shared DOM text content [frontend/assets/ts/core/dom/textContent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceContentWithFade } from '@core/animations/contentReplacement.ts';

const TEXT_NODE_TYPE = 3;

const applyImmediateTextContent = (target: Element | DocumentFragment, value: string): boolean => {
    const firstChild = target.firstChild;
    if (firstChild && firstChild === target.lastChild && firstChild.nodeType === TEXT_NODE_TYPE) {
        if (firstChild.nodeValue === value) {
            return false;
        }
        firstChild.nodeValue = value;
        return true;
    }
    if (!firstChild) {
        if (!value) {
            return false;
        }
        target.appendChild(target.ownerDocument.createTextNode(value));
        return true;
    }
    target.textContent = value;
    return true;
};

const isFadingTextTarget = (target: Element): boolean => target.matches('.toggle-label, .ui-collection-card__toggle-label, .page-header-title');

const applyTextContent = (target: Element | DocumentFragment, value: string): boolean => {
    if (target instanceof Element && isFadingTextTarget(target)) {
        return replaceContentWithFade(target, value, (text) => {
            applyImmediateTextContent(target, text);
        });
    }
    return applyImmediateTextContent(target, value);
};

export { applyTextContent, isFadingTextTarget };
