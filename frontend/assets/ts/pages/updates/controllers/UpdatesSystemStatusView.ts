/* SoAI - Updates page system status view [frontend/assets/ts/pages/updates/controllers/UpdatesSystemStatusView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { UpdatesSystemControllerHost } from '@pages/updates/controllers/UpdatesSystemControllerContract.ts';
import { buildUpdatesReleaseNotesMarkup, buildUpdatesSummaryMarkup } from '@pages/updates/controllers/UpdatesSystemMarkupBuilder.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import type { NormalizedUpdatePayload, UpdatesPageNoticeTone, UpdatesUiRefs } from '@pages/updates/types.ts';

type PageNoticeUiRefs = Pick<UpdatesUiRefs, 'pageNotice' | 'pageNoticeIndicator' | 'pageNoticeHeading' | 'pageNoticeDetail'>;
type SystemUiRefs = Pick<UpdatesUiRefs, 'statusIcon' | 'statusSpinner' | 'statusHeading' | 'statusDetail' | 'detailsSection' | 'summaryContainer' | 'notesContainer' | 'notesBody'>;
type StatusTextHost = {
    updateText: (element: Element, text: string) => void;
    toggleHidden: (element: Element, hidden: boolean) => void;
};

const NOTICE_TONE_CLASSES: readonly UpdatesPageNoticeTone[] = Object.freeze(['grey', 'green', 'blue', 'orange', 'red']);

const setUpdatesPageNotice = (host: StatusTextHost, ui: PageNoticeUiRefs, value: { tone: UpdatesPageNoticeTone; heading: string; detail: string }): void => {
    ui.pageNoticeIndicator.classList.remove(...NOTICE_TONE_CLASSES);
    ui.pageNoticeIndicator.classList.add(value.tone);
    host.updateText(ui.pageNoticeHeading, value.heading);
    host.updateText(ui.pageNoticeDetail, value.detail);
    host.toggleHidden(ui.pageNoticeDetail, !value.detail);
    host.toggleHidden(ui.pageNotice, false);
};

const setUpdatesSystemStatus = (dependencies: { ui: SystemUiRefs; updateText: (element: Element, text: string) => void; toggleHidden: (element: Element, hidden: boolean) => void; heading: string; detail: string; error?: boolean | undefined; loading?: boolean | undefined }): void => {
    dependencies.updateText(dependencies.ui.statusHeading, dependencies.heading);
    dependencies.updateText(dependencies.ui.statusDetail, dependencies.detail);
    dependencies.toggleHidden(dependencies.ui.statusIcon, dependencies.error !== true);
    dependencies.toggleHidden(dependencies.ui.statusSpinner, dependencies.loading !== true);
    dependencies.toggleHidden(dependencies.ui.statusDetail, !dependencies.detail);
};

const clearUpdatesSystemDetails = (dependencies: { ui: SystemUiRefs; toggleHidden: (element: Element, hidden: boolean) => void; updateHTML: (element: Element, html: TrustedHtml, options?: { escape?: boolean }) => void }): void => {
    dependencies.toggleHidden(dependencies.ui.detailsSection, true);
    dependencies.updateHTML(dependencies.ui.summaryContainer, EMPTY_UI_HTML);
    dependencies.updateHTML(dependencies.ui.notesBody, EMPTY_UI_HTML);
    dependencies.toggleHidden(dependencies.ui.notesContainer, true);
};

const renderUpdatesSystemDetails = (host: UpdatesSystemControllerHost, ui: SystemUiRefs, update: NormalizedUpdatePayload, saved = false): void => {
    const markup = buildUpdatesSummaryMarkup({
        update,
        savedLabel: saved ? i18n.t('updates.history.saved') : undefined,
        unknownLabel: i18n.t('updates.unknown'),
        updatesAvailableLabel: i18n.t('updates.sections.system.updatesAvailable', { count: 1 }),
        upToDateLabel: i18n.t('updates.badges.upToDate'),
        sectionTitle: i18n.t('updates.sections.system.title'),
        currentVersionLabel: i18n.t('updates.sections.system.current_version'),
        latestVersionLabel: i18n.t('updates.metadata.latest_version'),
        publishedLabel: i18n.t('updates.metadata.published'),
        releaseLinkLabel: i18n.t('updates.metadata.viewRelease'),
        installActionLabel: i18n.t('updates.actions.installUpdate'),
        installActionAriaLabel: i18n.t('updates.ariaLabels.installUpdate'),
        sanitizeHtml: host.sanitizeHtml,
        sanitizeAttribute: host.sanitizeAttribute,
        sanitizeUrl: host.sanitizeUrl,
        getIconSync: host.getIconSync,
        iconOptions: { size: 12, strokeWidth: 1.2 }
    });
    host.updateHTML(ui.summaryContainer, markup, { escape: false });
    const notes = buildUpdatesReleaseNotesMarkup({
        update,
        sanitizeHtml: host.sanitizeHtml,
        renderMarkdown: host.renderMarkdown,
        partialLabel: i18n.t('updates.notes.partial')
    });
    host.updateHTML(ui.notesBody, notes.html, { escape: false });
    host.toggleHidden(ui.notesContainer, !notes.hasNotes);
};

export { renderUpdatesSystemDetails, clearUpdatesSystemDetails, setUpdatesPageNotice, setUpdatesSystemStatus };
