/* SoAI - Core application update view [frontend/assets/ts/pages/updates/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { UPDATES_ACTION_CHECK } from '@pages/updates/actions.ts';

type GetIconSync = (iconName: IconName, options?: IconOptions) => TrustedHtml;
type GenerateStandardHeader = (options: GenerateStandardHeaderOptions) => TrustedHtml;

interface UpdatesPageViewDependencies {
    generateStandardHeader: GenerateStandardHeader;
    getIconSync: GetIconSync;
    productMarkup: TrustedHtml | null;
}

const renderUpdatesPageView = (dependencies: UpdatesPageViewDependencies): TrustedHtml => {
    const checkUpdatesIcon = dependencies.getIconSync('refresh', { size: 24, strokeWidth: 1.5 });
    const failureIcon = renderIconSlot(
        dependencies.getIconSync('close', {
            size: 18,
            strokeWidth: 2,
            stroke: 'var(--status-red)'
        }),
        { className: 'status-failure-icon-symbol' }
    );
    const header = dependencies.generateStandardHeader({
        title: i18n.t('updates.title'),
        description: i18n.t('updates.description'),
        floating: true,
        contentAreaClass: 'page-content-area updates-content',
        contentLayout: 'sections',
        actions: [
            {
                type: 'button',
                content: uiHtml`${checkUpdatesIcon}<span data-button-text>${i18n.t('updates.actions.checkUpdates')}</span>`,
                variant: 'ui-variant-neutral',
                class: 'updates-check-button',
                id: 'checkUpdatesBtn',
                attributes: { 'data-action': UPDATES_ACTION_CHECK },
                ariaLabel: i18n.t('updates.ariaLabels.checkUpdates')
            }
        ]
    });
    const productMarkup = dependencies.productMarkup?.html ?? '';
    const content = `
        <div class="updates-layout">
            <section class="updates-page-notice" id="updatesPageNotice" aria-live="polite">
                <div class="status-body" id="updatesPageNoticeBody">
                    <div class="status-copy" data-presence-morph>
                        <span class="status-indicator grey" id="updatesPageNoticeIndicator" aria-hidden="true"></span>
                        <div class="status-heading-row"><div class="status-heading" id="updatesPageNoticeHeading">${i18n.t('updates.status.idle')}</div></div>
                        <div class="status-detail u-hidden" id="updatesPageNoticeDetail"></div>
                    </div>
                </div>
                <div class="updates-page-progress u-hidden" id="updatesPageProgress"></div>
            </section>
            <section class="updates-status u-hidden" id="updatesStatus" data-presence data-presence-atomic data-presence-morph aria-live="polite">
                <div class="updates-application-header">
                    <div>
                        <h2 class="updates-application-title">${i18n.t('updates.application.title')}</h2>
                        <p class="updates-application-description">${i18n.t('updates.application.description')}</p>
                    </div>
                </div>
                <div class="status-body">
                    <div class="status-copy">
                        <div class="status-heading-row">
                            <span class="status-spinner loading-spinner u-hidden" id="updatesStatusSpinner" aria-hidden="true"></span>
                            <span class="status-failure-icon u-hidden" id="updatesStatusIcon" aria-hidden="true">${failureIcon}</span>
                            <div class="status-heading" id="updatesStatusHeading"></div>
                        </div>
                        <div class="status-detail u-hidden" id="updatesStatusDetail"></div>
                    </div>
                </div>
                <p class="updates-history u-hidden" id="updatesHistoryText" data-presence></p>
            </section>
            <section class="updates-details u-hidden" id="updatesDetails" data-presence data-presence-atomic>
                <div class="update-summary" id="updateSummary"></div>
                <div class="release-notes u-hidden" id="releaseNotesContainer" data-presence data-presence-atomic>
                    <div class="release-notes-header"><h3 id="releaseNotesTitle">${i18n.t('updates.metadata.release_notes')}</h3></div>
                    <div class="release-notes-body" id="release_notes"></div>
                </div>
            </section>
            <section class="update-summary u-hidden" id="backendUpdates" data-presence data-presence-atomic aria-live="polite"></section>
            ${productMarkup}
        </div>
    `;
    return toTrustedUiHtml(header.html.replace('<!-- Page content goes here -->', content));
};

export { renderUpdatesPageView };
