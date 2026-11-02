/* SoAI - Pane switcher modal using the shared presentation scaffold [frontend/assets/ts/core/pagepanes/modal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { PAGE_PANE_RECOVER } from '@core/pagepanes/actions.ts';

const PAGE_PANE_MODAL_ID = 'page-panes-modal';

const PAGE_PANE_MODAL_DEFINITION: ModalDefinition = {
    id: PAGE_PANE_MODAL_ID,
    layout: 'md',
    resizable: false,
    allowFullscreen: false,
    initialFocusSelector: `${modalUiSelector(PAGE_PANE_MODAL_ID, 'list')} [aria-current='page']`,
    createElement: () => {
        const modalId = PAGE_PANE_MODAL_ID;
        const header = renderStandardModalHeader({ modalId, title: i18n.t('pagePanes.title'), localizeTitle: false, closeLabel: i18n.t('common.close') });
        const body = renderModalBody(uiHtml`<div class="page-pane-switcher"><div id="${uiAttr(modalUiId(modalId, 'list'))}" class="page-pane-switcher__list" role="list"></div><p id="${uiAttr(modalUiId(modalId, 'status'))}" class="page-pane-switcher__notice" role="status" hidden></p><p id="${uiAttr(modalUiId(modalId, 'persistence'))}" class="page-pane-switcher__notice" role="status" hidden></p><section class="page-pane-switcher__section" aria-labelledby="${uiAttr(modalUiId(modalId, 'label'))}"><h3 id="${uiAttr(modalUiId(modalId, 'label'))}" class="page-pane-switcher__heading" data-modal-localize="text">${i18n.t('pagePanes.choosePage')}</h3><div id="${uiAttr(modalUiId(modalId, 'targets'))}" class="page-pane-switcher__targets" role="group" aria-labelledby="${uiAttr(modalUiId(modalId, 'label'))}"></div></section></div>`);
        const footer = renderSplitModalFooter({ left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.close') }), right: renderModalFooterActionButton({ id: modalUiId(modalId, 'recover'), action: PAGE_PANE_RECOVER, text: i18n.t('pagePanes.saveCurrentLayout'), className: 'u-hidden', localize: false }) });
        return createModalElement({ id: modalId, header, body, footer });
    }
};

export { PAGE_PANE_MODAL_ID, PAGE_PANE_MODAL_DEFINITION };
