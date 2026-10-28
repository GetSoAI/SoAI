/* SoAI - Shared prompts picker modal [frontend/assets/ts/features/prompts/modals/promptsPickerModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { renderSearchFieldActions } from '@core/ui/searchField.ts';
import { PROMPTS_PICKER_MODAL_ID } from '@features/prompts/modals/constants.ts';

const renderPromptsPickerBody = (modalId: string): ReturnType<typeof uiHtml> => {
    const searchInputId = modalUiId(modalId, 'search');
    const searchButtonId = modalUiId(modalId, 'search-button');
    const resultsId = modalUiId(modalId, 'results');
    const statusId = modalUiId(modalId, 'status');
    const placeholder = uiAttr(i18n.t('prompts.searchPlaceholder'));
    const searchLabel = uiAttr(i18n.t('prompts.picker.search'));
    return uiHtml`
        <div class="form-group setting-change-surface setting-change-surface--child-selection prompts-picker-surface">
            <div class="prompts-picker" data-prompts-picker>
                <div class="form-row-split form-row-split--search ui-collection-search-row">
                    <div class="form-col-main ui-collection-search-row__field">
                        <div class="searchbar-container searchbar-container--collection">
                            <input type="text" id="${searchInputId}" class="form-input searchbar-input prompts-picker-search-input" placeholder="${placeholder}" autocomplete="off" data-modal-localize="placeholder">
                            ${renderSearchFieldActions()}
                        </div>
                    </div>
                    <div class="form-col-secondary form-col-action ui-collection-search-row__action">
                        <button class="ui-button" id="${searchButtonId}" type="button" aria-label="${searchLabel}" data-tooltip="${searchLabel}" data-modal-localize="text aria-label data-tooltip">${i18n.t('prompts.picker.search')}</button>
                    </div>
                </div>
                <div class="prompts-picker-status" id="${statusId}" aria-live="polite"></div>
                <div class="prompts-picker-results" id="${resultsId}"></div>
            </div>
        </div>
    `;
};

const promptsPickerModalDefinition: ModalDefinition = {
    id: PROMPTS_PICKER_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: modalUiSelector(PROMPTS_PICKER_MODAL_ID, 'search'),
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = PROMPTS_PICKER_MODAL_ID;
        const titleId = modalUiId(modalId, 'title');
        const manageButtonId = modalUiId(modalId, 'manage');
        const closeLabel = i18n.t('common.close');
        const manageLabel = i18n.t('prompts.picker.manage');
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('prompts.picker.title'),
            description: i18n.t('prompts.picker.help'),
            closeLabel,
            titleId
        });
        const body = renderModalBody(renderPromptsPickerBody(modalId), { className: 'modal-body--sectioned prompts-picker-modal-body' });
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
            right: renderModalFooterActionButton({ id: manageButtonId, text: manageLabel, variant: 'neutral' })
        });
        return createModalElement({
            id: modalId,
            rootAttributes: { 'data-page-scope': 'prompts' },
            header,
            body,
            footer
        });
    }
};

export { promptsPickerModalDefinition };
