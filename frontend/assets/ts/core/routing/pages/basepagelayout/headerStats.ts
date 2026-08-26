/* SoAI - Shared routing header stats [frontend/assets/ts/core/routing/pages/basepagelayout/headerStats.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

const HEADER_STAT_CARD_SELECTOR = '.ui-page-header-stats__card';
const HEADER_STAT_LABEL_SELECTOR = '.stat-label';
const HEADER_STAT_CARD_HIDDEN_CLASS = 'ui-page-header-stats__card--hidden';
const HEADER_STAT_CARD_SUPPRESSED_CLASS = 'ui-page-header-stats__card--suppressed';

type HeaderStatTextHost = PageDomOwnerHost;

type HeaderStatClassHost = PageDomOwnerHost;

const resolveHeaderStatCard = (element: Element | null): HTMLElement | null => {
    if (!(element instanceof Element)) {
        return null;
    }
    const card = element.closest(HEADER_STAT_CARD_SELECTOR);
    return card instanceof HTMLElement ? card : null;
};

const requireHeaderStatCard = (element: Element, context: string): HTMLElement => {
    const card = resolveHeaderStatCard(element);
    if (!card) {
        throw new Error(`${context} stat card is missing`);
    }
    return card;
};

const resolveHeaderStatLabel = (card: Element | null): HTMLElement | null => {
    if (!(card instanceof Element)) {
        return null;
    }
    const label = dom.resolve(HEADER_STAT_LABEL_SELECTOR, card);
    return label instanceof HTMLElement ? label : null;
};

const updateHeaderStatCard = (host: HeaderStatTextHost, valueElement: Element, label: string, value: string): void => {
    host.pageDom.updateText(valueElement, value);
    const labelElement = resolveHeaderStatLabel(resolveHeaderStatCard(valueElement));
    if (labelElement) {
        host.pageDom.updateText(labelElement, label);
    }
};

const setHeaderStatCardHidden = (host: HeaderStatClassHost, valueElement: Element, hidden: boolean): void => {
    const card = resolveHeaderStatCard(valueElement);
    if (card) {
        host.pageDom.toggleClass(card, HEADER_STAT_CARD_HIDDEN_CLASS, hidden);
    }
};

const setHeaderStatCardSuppressed = (host: HeaderStatClassHost, valueElement: Element, suppressed: boolean): void => {
    const card = resolveHeaderStatCard(valueElement);
    if (card) {
        host.pageDom.toggleClass(card, HEADER_STAT_CARD_SUPPRESSED_CLASS, suppressed);
    }
};

export { HEADER_STAT_CARD_HIDDEN_CLASS, HEADER_STAT_CARD_SELECTOR, HEADER_STAT_CARD_SUPPRESSED_CLASS, requireHeaderStatCard, resolveHeaderStatCard, resolveHeaderStatLabel, setHeaderStatCardHidden, setHeaderStatCardSuppressed, updateHeaderStatCard };
