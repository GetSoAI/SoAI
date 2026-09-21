/* SoAI - Archived conversations modal scaffold [frontend/assets/ts/features/chat/modals/archived/archivedConversationsModalScaffold.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { renderLabelAttributes, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderSearchFieldActions } from '@core/ui/searchField.ts';
import { ARCHIVED_CONVERSATIONS_MODAL_ID } from '@features/chat/modals/constants.ts';

const renderArchivedConversationsModalScaffold = (): { header: TrustedHtml; body: TrustedHtml; footer: TrustedHtml } => {
    const modalId = ARCHIVED_CONVERSATIONS_MODAL_ID;
    const searchLabel = i18n.t('chat.archive.searchPlaceholder');
    const searchActions = renderSearchFieldActions();
    const body = renderModalBody(
        toTrustedUiHtml(
            `<div class="archived-conversations-modal"><div class="archived-conversations-search searchbar-container searchbar-container--collection"><input type="search" class="archived-conversations-search-input form-input searchbar-input" placeholder="${uiAttr(searchLabel).html}" aria-label="${uiAttr(searchLabel).html}">${searchActions.html}</div><div class="archived-toolbar-container"><div class="archived-toolbar-metrics"><span class="archived-toolbar-total"></span><span class="archived-toolbar-selected u-hidden"></span></div><div class="archived-toolbar-actions"><button type="button" class="archived-toolbar-select-btn ui-icon-button" data-action="archive:enter-select-mode" ${renderLabelAttributes(i18n.t('chat.toolbar.select'))}></button></div><div class="archived-toolbar-batch-actions u-hidden"><button type="button" class="archived-toolbar-unarchive-btn ui-icon-button u-hidden" data-action="archive:batch-unarchive" ${renderLabelAttributes(i18n.t('chat.toolbar.batchUnarchive'))} disabled></button><button type="button" class="archived-toolbar-delete-btn ui-icon-button ui-button ui-variant-danger u-hidden" data-action="archive:batch-delete" ${renderLabelAttributes(i18n.t('chat.toolbar.batchDelete'))} disabled></button><button type="button" class="archived-toolbar-exit-select-btn ui-icon-button" data-action="archive:exit-select-mode" ${renderLabelAttributes(i18n.t('chat.toolbar.exitSelect'))}></button></div></div><div class="archived-conversations-scroll"><div class="archived-conversations-list"></div><div class="archived-conversations-status" aria-live="polite"></div></div></div>`
        ),
        { className: 'archived-conversations-modal-body' }
    );
    return {
        header: renderStandardModalHeader({
            modalId,
            title: i18n.t('chat.archive.title'),
            closeLabel: i18n.t('common.close'),
            titleId: modalUiId(modalId, 'title')
        }),
        body,
        footer: renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.close') })
        })
    };
};

export { renderArchivedConversationsModalScaffold };
