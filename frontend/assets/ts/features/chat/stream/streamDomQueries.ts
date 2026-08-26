/* SoAI - Chat feature stream DOM queries [frontend/assets/ts/features/chat/stream/streamDomQueries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

type KeyedElement = {
    key: string;
    element: HTMLElement;
};

const collectMatchingElements = (root: Element, selector: string): HTMLElement[] => {
    const results: HTMLElement[] = [];
    if (root instanceof HTMLElement && root.matches(selector)) {
        results.push(root);
    }
    for (const candidate of dom.resolveAll(selector, root)) {
        if (candidate instanceof HTMLElement) {
            results.push(candidate);
        }
    }
    return results;
};

const collectKeyedElements = (root: Element, selector: string, attributeName: string): KeyedElement[] => {
    const keyed: KeyedElement[] = [];
    for (const element of collectMatchingElements(root, selector)) {
        const rawKey = element.getAttribute(attributeName);
        if (!rawKey) {
            continue;
        }
        const key = rawKey.trim();
        if (!key) {
            continue;
        }
        keyed.push({ key, element });
    }
    return keyed;
};

export { collectKeyedElements, collectMatchingElements };
export type { KeyedElement };
