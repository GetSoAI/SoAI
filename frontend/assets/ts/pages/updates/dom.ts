/* SoAI - Core application update DOM contracts [frontend/assets/ts/pages/updates/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { UpdatesUiRefs } from '@pages/updates/types.ts';

const requireUpdatesUi = (pageDom: PageDom): UpdatesUiRefs => ({
    pageNotice: pageDom.requireHTMLElement('#updatesPageNotice'),
    pageNoticeIndicator: pageDom.requireHTMLElement('#updatesPageNoticeIndicator'),
    pageNoticeHeading: pageDom.requireHTMLElement('#updatesPageNoticeHeading'),
    pageNoticeDetail: pageDom.requireHTMLElement('#updatesPageNoticeDetail'),
    statusIcon: pageDom.requireHTMLElement('#updatesStatusIcon'),
    statusSpinner: pageDom.requireHTMLElement('#updatesStatusSpinner'),
    statusHeading: pageDom.requireHTMLElement('#updatesStatusHeading'),
    statusDetail: pageDom.requireHTMLElement('#updatesStatusDetail'),
    detailsSection: pageDom.requireHTMLElement('#updatesDetails'),
    summaryContainer: pageDom.requireHTMLElement('#updateSummary'),
    notesContainer: pageDom.requireHTMLElement('#releaseNotesContainer'),
    notesBody: pageDom.requireHTMLElement('#release_notes')
});

const optionalUpdatesNotesBody = (pageDom: PageDom): HTMLElement | null => pageDom.optionalHTMLElement('#release_notes');

export { optionalUpdatesNotesBody, requireUpdatesUi };
