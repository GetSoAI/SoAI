/* SoAI - Shared DOM parse single root element [frontend/assets/ts/core/dom/parseSingleRootElement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createHtmlFragment } from '@core/dom/html.ts';
import type { TrustedHtml } from '@core/security/public.ts';

const ELEMENT_NODE_TYPE = 1;
const TEXT_NODE_TYPE = 3;
const COMMENT_NODE_TYPE = 8;

const parseSingleRootElement = (inputArguments: { documentRef: Document; html: TrustedHtml; context: Element | Document }): HTMLElement | null => {
    const fragment = createHtmlFragment({ documentRef: inputArguments.documentRef, html: inputArguments.html.html, context: inputArguments.context });
    const elements = Array.from(fragment.children);
    if (elements.length !== 1) {
        return null;
    }
    for (const child of fragment.childNodes) {
        if (child.nodeType === TEXT_NODE_TYPE && child.textContent !== null && child.textContent.trim()) {
            return null;
        }
        if (child.nodeType !== ELEMENT_NODE_TYPE && child.nodeType !== TEXT_NODE_TYPE && child.nodeType !== COMMENT_NODE_TYPE) {
            return null;
        }
    }
    const node = elements[0];
    return node instanceof HTMLElement ? node : null;
};

export { parseSingleRootElement };
