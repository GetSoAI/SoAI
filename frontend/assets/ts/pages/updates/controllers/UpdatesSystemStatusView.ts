/* SoAI - Updates page system status view [frontend/assets/ts/pages/updates/controllers/UpdatesSystemStatusView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import type { UpdatesPageNoticeTone, UpdatesUiRefs } from '@pages/updates/types.ts';

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

export { clearUpdatesSystemDetails, setUpdatesPageNotice, setUpdatesSystemStatus };
