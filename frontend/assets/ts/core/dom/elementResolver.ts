/* SoAI - Standardized ElementResolver implementation for strict DOM contracts [frontend/assets/ts/core/dom/elementResolver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ElementResolver } from '@core/dom/typedElements.ts';
import { isElementNodeLike, isHTMLElementNodeLike } from '@core/dom/domEnvironment.ts';

const createElementResolver = (root: Element, labelPrefix: string): ElementResolver => {
    if (!isElementNodeLike(root)) {
        throw new Error('createElementResolver requires a root Element');
    }
    const prefix = String(labelPrefix || '').trim();
    if (!prefix) {
        throw new Error('createElementResolver requires a non-empty labelPrefix');
    }
    return {
        requireHTMLElement: (selector: string, context?: Element): HTMLElement => {
            const scope = context ?? root;
            const resolved = scope.querySelector(selector);
            if (!isHTMLElementNodeLike(resolved)) {
                throw new Error(`${prefix} required HTMLElement missing: ${selector}`);
            }
            return resolved;
        }
    };
};

export { createElementResolver };
