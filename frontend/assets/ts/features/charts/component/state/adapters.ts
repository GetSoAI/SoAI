/* SoAI - Charts feature adapters [frontend/assets/ts/features/charts/component/state/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isFunction } from '@core/typeGuards.ts';

const getStyleSources = (element: HTMLElement): CSSStyleDeclaration[] => {
    const doc = element.ownerDocument;
    const win = doc.defaultView;
    if (!win || !isFunction(win.getComputedStyle)) {
        throw new Error('Chart requires window.getComputedStyle');
    }
    const currentTime = element.parentElement || doc.documentElement;
    const sources: Array<CSSStyleDeclaration | null> = [win.getComputedStyle(element), currentTime !== element && currentTime ? win.getComputedStyle(currentTime) : null, currentTime !== doc.documentElement ? win.getComputedStyle(doc.documentElement) : null];
    return sources.filter((stringValue): stringValue is CSSStyleDeclaration => stringValue !== null);
};

const readCssVariable = (src: readonly CSSStyleDeclaration[], ids: string | string[]): string => {
    for (const stringValue of src) {
        for (const candidateValue of isArray(ids) ? ids : [ids]) {
            const value = stringValue.getPropertyValue(candidateValue)?.trim();
            if (value) return value;
        }
    }
    return '';
};

export { getStyleSources, readCssVariable };
