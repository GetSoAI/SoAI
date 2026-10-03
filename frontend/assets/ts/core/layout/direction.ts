/* SoAI - Element-relative inline direction and scroll coordinates [frontend/assets/ts/core/layout/direction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getComputedStyleStrict } from '@core/environment/public.ts';
import { normalizeScrollPosition } from '@core/dom/scrollGeometry.ts';

const isRtl = (element: Element): boolean => getComputedStyleStrict(element).direction === 'rtl';

const inlineDelta = (delta: number, element: Element): number => (isRtl(element) ? -delta : delta);

const readScrollInlineStart = (element: HTMLElement): number => normalizeScrollPosition(inlineDelta(element.scrollLeft, element), element.scrollWidth - element.clientWidth);

const scrollToInlineStart = (element: HTMLElement, position: number, behavior: ScrollBehavior = 'auto'): void => {
    const boundedPosition = normalizeScrollPosition(position, element.scrollWidth - element.clientWidth);
    if (behavior === 'instant') {
        element.scrollLeft = inlineDelta(boundedPosition, element);
        return;
    }
    element.scrollTo({ left: inlineDelta(boundedPosition, element), behavior });
};

const scrollByInline = (element: HTMLElement, delta: number, behavior: ScrollBehavior = 'auto'): void => {
    const currentPosition = readScrollInlineStart(element);
    const targetPosition = normalizeScrollPosition(currentPosition + delta, element.scrollWidth - element.clientWidth);
    if (behavior === 'instant') {
        scrollToInlineStart(element, targetPosition, behavior);
        return;
    }
    element.scrollBy({ left: inlineDelta(targetPosition - currentPosition, element), behavior });
};

const resolveInlineArrowStep = (key: string, element: Element): -1 | 0 | 1 => {
    if (key === 'ArrowLeft') return isRtl(element) ? 1 : -1;
    if (key === 'ArrowRight') return isRtl(element) ? -1 : 1;
    return 0;
};

export { inlineDelta, isRtl, readScrollInlineStart, resolveInlineArrowStep, scrollByInline, scrollToInlineStart };
