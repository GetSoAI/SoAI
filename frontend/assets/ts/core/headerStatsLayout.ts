/* SoAI - Shared frontend header stats layout [frontend/assets/ts/core/headerStatsLayout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';

const DEFAULT_MIN_WIDTH = 240;
const ADAPTIVE_STAT_VALUE_SELECTOR = '[data-full-value][data-compact-value]';

const toNumber = (value: string | undefined): number | null => {
    const count = Number.parseFloat(String(value));
    return Number.isFinite(count) ? count : null;
};

const resolveMinWidth = (container: HTMLElement, sample: HTMLElement | null): number => {
    const containerStyle = getComputedStyleStrict(container);
    const varWidth = toNumber(containerStyle?.getPropertyValue('--ui-page-header-stats-min-width'));
    const sampleStyle = sample ? getComputedStyleStrict(sample) : null;
    const cardWidth = toNumber(sampleStyle?.minWidth);
    return (cardWidth && cardWidth > 0 ? cardWidth : null) ?? (varWidth && varWidth > 0 ? varWidth : null) ?? DEFAULT_MIN_WIDTH;
};

const resolveGap = (container: HTMLElement): number => {
    const style = getComputedStyleStrict(container);
    const gap = toNumber(style?.columnGap) ?? toNumber(style?.gap) ?? 0;
    return gap > 0 ? gap : 0;
};

interface CalculateVisibleStatsParameters {
    availableWidth: number;
    minWidth: number;
    gap: number;
    totalCards: number;
}

const calculateVisibleStats = ({ availableWidth, minWidth, gap, totalCards }: CalculateVisibleStatsParameters): number => {
    const width = Number.isFinite(availableWidth) && availableWidth > 0 ? availableWidth : 0;
    const min = Number.isFinite(minWidth) && minWidth > 0 ? minWidth : DEFAULT_MIN_WIDTH;
    const safeGap = Number.isFinite(gap) && gap >= 0 ? gap : 0;
    const count = Number.isFinite(totalCards) && totalCards > 0 ? Math.floor(totalCards) : 0;
    if (!count) return 0;
    const capacity = Math.floor((width + safeGap) / (min + safeGap));
    const visible = clampNumber(capacity || 1, 1, count);
    return visible;
};

const applyAdaptiveStatValues = (container: HTMLElement): void => {
    dom.resolveAll(ADAPTIVE_STAT_VALUE_SELECTOR, container).forEach((element) => {
        if (!(element instanceof HTMLElement)) {
            throw new TypeError('Adaptive header stat value must be an HTML element');
        }
        const fullValue = element.dataset['fullValue'];
        const compactValue = element.dataset['compactValue'];
        if (fullValue === undefined || compactValue === undefined) {
            throw new Error('Adaptive header stat value requires full and compact text');
        }
        element.textContent = fullValue;
        if (element.scrollWidth > element.clientWidth) {
            element.textContent = compactValue;
        }
    });
};

const applyHeaderStatsLayout = (container: HTMLElement | null): number => {
    const cards = container ? dom.resolveAll('.ui-page-header-stats__card:not(.ui-page-header-stats__card--suppressed)', container) : [];
    if (!cards.length) return 0;
    const containerRef = container;
    if (!containerRef) {
        return 0;
    }
    const firstCard = cards[0];
    const sample = firstCard instanceof HTMLElement ? firstCard : null;
    const minWidth = resolveMinWidth(containerRef, sample);
    const gap = resolveGap(containerRef);
    const availableWidth = containerRef.clientWidth || measureLayoutBox(containerRef).width || 0;
    if (availableWidth <= 0) {
        return cards.filter((card) => !card.classList.contains('ui-page-header-stats__card--hidden')).length;
    }

    containerRef.classList.add('ui-page-header-stats--compact');
    const visible = calculateVisibleStats({
        availableWidth,
        minWidth,
        gap,
        totalCards: cards.length
    });
    containerRef.style.setProperty('--header-stats-columns', `${visible}`);
    cards.forEach((card: Element, index: number) => {
        const hidden = index >= visible;
        card.classList.toggle('ui-page-header-stats__card--hidden', hidden);
        card.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    });
    applyAdaptiveStatValues(containerRef);
    return visible;
};

export { applyHeaderStatsLayout, calculateVisibleStats };

export type { CalculateVisibleStatsParameters };
