/* SoAI - Shared layout title manager rendering [frontend/assets/ts/core/layout/header/titlemanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { NavigationDetail, TitleManagerHost } from '@core/layout/header/titlemanager/types.ts';

const normalizeTitle = (value: string): string => {
    return value.replace(/\s+/g, ' ').trim();
};

const formatTabBrandName = (brand: string): string => {
    const normalizedBrand = normalizeTitle(brand) || 'SoAI';
    if (normalizedBrand === 'SoAI OS') {
        return 'SoAI OS';
    }
    return normalizedBrand;
};

const resolveNavigationTitle = (detail: NavigationDetail, component: string, brand: string, headerless: boolean): string => {
    if (isString(detail.title) && detail.title) {
        return detail.title;
    }
    if (headerless) {
        return component.charAt(0).toUpperCase() + component.slice(1);
    }
    return brand;
};

const setPageTitleDisplay = (header: TitleManagerHost, value: string, brand: string): void => {
    const titleNode = header.getDom('pageTitle');
    if (!titleNode) {
        return;
    }
    const normalized = normalizeTitle(value) || brand;
    const isSoaiBrand = normalized === 'SoAI' || normalized === 'SoAI OS';
    const logoSlot = header.optionalHTMLElement('.page-title-logo-slot', titleNode);
    const textNode = header.optionalHTMLElement('.page-title-text', titleNode);
    if (!logoSlot || !textNode) {
        throw new Error('Header page title requires logo and text elements');
    }
    header.updateText(textNode, isSoaiBrand ? '' : normalized);
    header.updateAttribute(titleNode, 'data-page-title-display', isSoaiBrand ? 'brand' : 'page');
    header.updateAttribute(titleNode, 'aria-label', normalized);
    setTooltipText(titleNode, normalized);
};

export { formatTabBrandName, normalizeTitle, resolveNavigationTitle, setPageTitleDisplay };
