/* SoAI - Shared routing collections rendering [frontend/assets/ts/core/routing/pages/collections/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject, isString } from '@core/typeGuards.ts';
import type { HeaderConfig, LayoutConfig } from '@core/routing/pages/collections/types.ts';
import { isTrustedHtml, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';

const composeCollectionLayout = (pageId: string, generateStandardHeader: (config: HeaderConfig) => TrustedHtml, { headerConfig, content = '' }: LayoutConfig): TrustedHtml => {
    if (!headerConfig || !isObject(headerConfig)) {
        throw new TypeError('Header config must be an object');
    }
    const headerMarkup = generateStandardHeader(headerConfig);
    if (!isTrustedHtml(headerMarkup)) {
        throw new TypeError(`CollectionManager.composeLayout() for page ${pageId}: generateStandardHeader() must return TrustedHtml`);
    }

    const header = headerMarkup.html;
    if (!header || (isString(header) && header.trim().length === 0)) {
        throw new Error(`CollectionManager.composeLayout() for page ${pageId}: generateStandardHeader() returned empty content - this indicates a critical layout generation failure`);
    }

    const insertionToken = '<!-- Page content goes here -->';
    const bodyMarkup = header.includes(insertionToken) ? header.replace(insertionToken, content) : `${header}${content}`;
    const result = bodyMarkup;

    if (!result || (isString(result) && result.trim().length === 0)) {
        throw new Error(`CollectionManager.composeLayout() for page ${pageId}: final layout is empty - header: ${header.length} chars, content: ${content.length} chars`);
    }

    return toTrustedUiHtml(result);
};

export { composeCollectionLayout };
