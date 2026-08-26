/* SoAI - Shared routing page header title [frontend/assets/ts/core/routing/pages/basepagelayout/pageHeaderTitle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { getDocument } from '@core/environment/public.ts';
import { dom } from '@core/dom/dom.ts';
import { MIDDLE_ELLIPSIS, splitMiddleEllipsisText, type MiddleEllipsisSegments } from '@core/primitives/text.ts';
import { uiAttr, uiText } from '@core/security/uiHtml.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

const PAGE_HEADER_TITLE_MAX_CHARACTERS = 45;
const PAGE_HEADER_TITLE_FULL_ATTRIBUTE = 'data-page-header-title-full';
const PAGE_HEADER_TITLE_MIDDLE_ATTRIBUTE = 'data-page-header-title-middle-ellipsis';

const normalizePageHeaderTitle = (value: string): string => value.replace(/\s+/g, ' ').trim();

const splitPageHeaderTitle = (value: string): MiddleEllipsisSegments => splitMiddleEllipsisText(normalizePageHeaderTitle(value), PAGE_HEADER_TITLE_MAX_CHARACTERS);

const readPageHeaderTitleText = (element: HTMLElement): string => {
    if (element.getAttribute(PAGE_HEADER_TITLE_MIDDLE_ATTRIBUTE) === 'true') {
        const attributeValue = element.getAttribute(PAGE_HEADER_TITLE_FULL_ATTRIBUTE);
        return normalizePageHeaderTitle(attributeValue ?? element.textContent ?? '');
    }
    return normalizePageHeaderTitle(element.textContent ?? '');
};

const buildSharedPageHeaderTitleAttributes = (segments: MiddleEllipsisSegments): string => {
    const full = uiAttr(segments.full).html;
    return ` data-tooltip="${full}" aria-label="${full}"`;
};

const buildPageHeaderTitleMarkup = (value: string): TrustedHtml => {
    const segments = splitPageHeaderTitle(value);
    const attributes = buildSharedPageHeaderTitleAttributes(segments);
    if (!segments.truncated) {
        return toTrustedUiHtml(`<h1 class="page-header-title"${attributes}>${uiText(segments.full).html}</h1>`);
    }
    return toTrustedUiHtml(`<h1 class="page-header-title" ${PAGE_HEADER_TITLE_FULL_ATTRIBUTE}="${uiAttr(segments.full).html}" ${PAGE_HEADER_TITLE_MIDDLE_ATTRIBUTE}="true"${attributes}>` + `<span class="page-header-title-segment page-header-title-segment--leading" aria-hidden="true">${uiText(segments.leading).html}</span>` + `<span class="page-header-title-ellipsis" aria-hidden="true">${MIDDLE_ELLIPSIS}</span>` + `<span class="page-header-title-segment page-header-title-segment--trailing" aria-hidden="true">${uiText(segments.trailing).html}</span>` + `</h1>`);
};

const hasRenderedTruncatedTitle = (element: HTMLElement, segments: MiddleEllipsisSegments): boolean => {
    if (element.getAttribute(PAGE_HEADER_TITLE_FULL_ATTRIBUTE) !== segments.full) {
        return false;
    }
    if (element.getAttribute(PAGE_HEADER_TITLE_MIDDLE_ATTRIBUTE) !== 'true') {
        return false;
    }
    if (element.children.length !== 3) {
        return false;
    }
    const leading = dom.resolve('.page-header-title-segment--leading', element);
    const ellipsis = dom.resolve('.page-header-title-ellipsis', element);
    const trailing = dom.resolve('.page-header-title-segment--trailing', element);
    return leading?.textContent === segments.leading && ellipsis?.textContent === MIDDLE_ELLIPSIS && trailing?.textContent === segments.trailing;
};

const applyPageHeaderTitleDisplay = (element: HTMLElement, value: string): string => {
    const segments = splitPageHeaderTitle(value);
    if (!segments.truncated) {
        const hasMiddleEllipsis = element.getAttribute(PAGE_HEADER_TITLE_MIDDLE_ATTRIBUTE) === 'true';
        const currentText = element.textContent ?? '';
        const currentTitle = element.getAttribute('data-tooltip') ?? '';
        const currentAriaLabel = element.getAttribute('aria-label') ?? '';
        if (!hasMiddleEllipsis && !element.hasAttribute(PAGE_HEADER_TITLE_FULL_ATTRIBUTE) && element.childElementCount === 0 && currentText === segments.full && currentTitle === segments.full && currentAriaLabel === segments.full) {
            return segments.full;
        }
        element.removeAttribute(PAGE_HEADER_TITLE_FULL_ATTRIBUTE);
        element.removeAttribute(PAGE_HEADER_TITLE_MIDDLE_ATTRIBUTE);
        setTooltipText(element, segments.full);
        element.setAttribute('aria-label', segments.full);
        element.textContent = segments.full;
        return segments.full;
    }
    if (hasRenderedTruncatedTitle(element, segments)) {
        return segments.full;
    }
    const documentRef = getDocument();
    const leading = documentRef.createElement('span');
    leading.className = 'page-header-title-segment page-header-title-segment--leading';
    leading.textContent = segments.leading;
    leading.setAttribute('aria-hidden', 'true');
    const ellipsis = documentRef.createElement('span');
    ellipsis.className = 'page-header-title-ellipsis';
    ellipsis.textContent = MIDDLE_ELLIPSIS;
    ellipsis.setAttribute('aria-hidden', 'true');
    const trailing = documentRef.createElement('span');
    trailing.className = 'page-header-title-segment page-header-title-segment--trailing';
    trailing.textContent = segments.trailing;
    trailing.setAttribute('aria-hidden', 'true');
    element.setAttribute(PAGE_HEADER_TITLE_FULL_ATTRIBUTE, segments.full);
    element.setAttribute(PAGE_HEADER_TITLE_MIDDLE_ATTRIBUTE, 'true');
    setTooltipText(element, segments.full);
    element.setAttribute('aria-label', segments.full);
    element.textContent = '';
    element.append(leading, ellipsis, trailing);
    return segments.full;
};

export { applyPageHeaderTitleDisplay, buildPageHeaderTitleMarkup, readPageHeaderTitleText };
