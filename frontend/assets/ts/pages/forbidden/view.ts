/* SoAI - Forbidden page rendering [frontend/assets/ts/pages/forbidden/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';

import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { FORBIDDEN_ACTION_GO_BACK, FORBIDDEN_ACTION_GO_DEFAULT_ROUTE } from '@pages/forbidden/actions.ts';
import type { ForbiddenViewDependencies } from '@pages/forbidden/types.ts';

export const renderForbiddenPageView = (dependencies: ForbiddenViewDependencies): TrustedHtml => {
    const header = dependencies.generateStandardHeader({
        containerClass: 'forbidden-page page-scrollable',
        title: i18n.t('pages.forbidden.title'),
        description: i18n.t('pages.forbidden.description'),
        floating: true,
        contentLayout: null
    });

    const icon = dependencies.getIconSync('error', { size: 48, strokeWidth: 1.5 });
    const message = dependencies.requestedPageTitle ? i18n.t('pages.forbidden.messageWithPage', { page: dependencies.requestedPageTitle }) : i18n.t('pages.forbidden.message');
    const backLabel = i18n.t('pages.forbidden.actions.back');
    const defaultRouteLabel = i18n.t('nav.dashboard');

    const content = uiHtml`<div id="forbidden-root">
        <div class="ui-empty-state">
            <div class="ui-empty-state__icon">${icon}</div>
            <h3>${i18n.t('pages.forbidden.heading')}</h3>
            <p>${message}</p>
            <div class="ui-empty-state__actions">
                <button type="button" class="ui-button ui-variant-neutral" data-action="${uiAttr(FORBIDDEN_ACTION_GO_BACK)}" aria-label="${uiAttr(backLabel)}" data-tooltip="${uiAttr(backLabel)}">${backLabel}</button>
                <button type="button" class="ui-button ui-variant-accent" data-action="${uiAttr(FORBIDDEN_ACTION_GO_DEFAULT_ROUTE)}" aria-label="${uiAttr(defaultRouteLabel)}" data-tooltip="${uiAttr(defaultRouteLabel)}">${defaultRouteLabel}</button>
            </div>
        </div>
    </div>`;

    return toTrustedUiHtml(header.html.replace('<!-- Page content goes here -->', content.html));
};
