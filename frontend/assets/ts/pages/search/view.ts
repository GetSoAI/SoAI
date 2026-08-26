/* SoAI - Search page rendering [frontend/assets/ts/pages/search/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';

type GenerateStandardHeaderFunctionValue = (options: GenerateStandardHeaderOptions) => TrustedHtml;

export const renderSearchPageView = (dependencies: { generateStandardHeader: GenerateStandardHeaderFunctionValue }): TrustedHtml => {
    const header = dependencies.generateStandardHeader({
        title: i18n.t('pages.search.title'),
        description: i18n.t('search.description'),
        floating: true,
        contentAreaClass: 'search-content',
        actions: [{ type: 'search' }],
        tabs: {
            containerId: 'search-tabs-container',
            html: EMPTY_UI_HTML
        },
        responsive: {
            mobile: {
                stackActions: true,
                hideElements: []
            }
        }
    });

    const content = `
        <div id="search-results" class="search-results"></div>
        <div id="no-results" class="no-results u-hidden">
        <div class="no-results-icon" id="no-results-icon"></div>
        <h3 id="no-results-title">${i18n.t('search.noResults.emptyTitle')}</h3>
        <p id="no-results-message">${i18n.t('search.noResults.emptyMessage')}</p>
        </div>
    `;

    return toTrustedUiHtml(header.html.replace('<!-- Page content goes here -->', content));
};
