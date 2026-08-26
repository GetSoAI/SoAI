/* SoAI - Unified content preview modal definition [frontend/assets/ts/core/ui/modals/contentpreview/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_BUTTON_ROLE_ATTRIBUTE } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { CONTENT_PREVIEW_ACTION_ATTR, CONTENT_PREVIEW_ACTIONS, CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS } from '@core/ui/modals/contentpreview/constants.ts';

const createContentPreviewModalElement = (): HTMLElement => {
    const modalId = CONTENT_PREVIEW_MODAL_ID;
    const titleId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.TITLE);
    const descriptionId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.DESCRIPTION);
    const colorContainerId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.COLOR_CONTAINER);
    const headerCloseButtonId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.HEADER_CLOSE);
    const footerId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.FOOTER);
    const textHostId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.TEXT_HOST);
    const textStatsId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.TEXT_STATS);
    const mediaHostId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.MEDIA_HOST);
    const closeButtonId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.CLOSE);
    const downloadButtonId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.DOWNLOAD);
    const copyButtonId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.COPY);
    const attachButtonId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.ATTACH);
    const openSourceButtonId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.OPEN_SOURCE);
    const enhanceButtonId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.ENHANCE);
    const editButtonId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.EDIT);
    const saveButtonId = modalUiId(modalId, CONTENT_PREVIEW_UI_TOKENS.SAVE);

    const closeLabel = i18n.t('common.close');
    const openSourceLabel = i18n.t('contentPreview.actions.openSource');
    const downloadLabel = i18n.t('fileExplorer.modal.download');
    const copyLabel = i18n.t('common.copy');
    const attachLabel = i18n.t('contentPreview.actions.attach');
    const enhanceLabel = i18n.t('common.ok');
    const editLabel = i18n.t('common.edit');
    const saveLabel = i18n.t('common.save');

    const header = renderStandardModalHeader({
        modalId,
        title: uiHtml``,
        titleId,
        description: '',
        descriptionId,
        titleGroupClassName: 'prompt-modal-header',
        closeLabel,
        closeId: headerCloseButtonId,
        closeAttributes: {
            [MODAL_HEADER_BUTTON_ROLE_ATTRIBUTE]: 'close',
            [CONTENT_PREVIEW_ACTION_ATTR]: CONTENT_PREVIEW_ACTIONS.CLOSE
        },
        leading: uiHtml`<div class="prompt-modal-header-left"><div class="prompt-modal-header-color u-hidden" id="${colorContainerId}" aria-hidden="true"></div>`,
        trailing: uiHtml`</div>`
    });

    const body = renderModalBody(uiHtml`
        <div class="prompt-modal-content">
            <div class="prompt-modal-content-editor">
                <div class="prompt-modal-content-text prompt-view-text" id="${textHostId}"></div>
                <dl class="content-preview-text-info glass-surface-light glass-surface--rounded u-hidden" id="${textStatsId}" aria-hidden="true"></dl>
                <div class="content-preview-media-host u-hidden" aria-hidden="true" id="${mediaHostId}"></div>
            </div>
        </div>
    `);

    const footer = renderSplitModalFooter({
        id: footerId,
        left: renderModalFooterCloseButton({ modalId, id: closeButtonId, text: closeLabel, attributes: { [CONTENT_PREVIEW_ACTION_ATTR]: CONTENT_PREVIEW_ACTIONS.CLOSE } }),
        right: uiHtml`
            ${renderModalFooterActionButton({ id: openSourceButtonId, text: openSourceLabel, className: 'u-hidden', ariaHidden: true, attributes: { [CONTENT_PREVIEW_ACTION_ATTR]: CONTENT_PREVIEW_ACTIONS.OPEN_SOURCE } })}
            ${renderModalFooterActionButton({ id: copyButtonId, text: copyLabel, variant: 'primary', attributes: { [CONTENT_PREVIEW_ACTION_ATTR]: CONTENT_PREVIEW_ACTIONS.COPY } })}
            ${renderModalFooterActionButton({ id: attachButtonId, text: attachLabel, variant: 'violet', className: 'u-hidden', ariaHidden: true, attributes: { [CONTENT_PREVIEW_ACTION_ATTR]: CONTENT_PREVIEW_ACTIONS.ATTACH } })}
            ${renderModalFooterActionButton({ id: downloadButtonId, text: downloadLabel, variant: 'accent', attributes: { [CONTENT_PREVIEW_ACTION_ATTR]: CONTENT_PREVIEW_ACTIONS.DOWNLOAD } })}
            ${renderModalFooterActionButton({ id: enhanceButtonId, text: enhanceLabel, variant: 'violet', className: 'u-hidden', ariaHidden: true, attributes: { [CONTENT_PREVIEW_ACTION_ATTR]: CONTENT_PREVIEW_ACTIONS.ENHANCE } })}
            ${renderModalFooterActionButton({ id: editButtonId, text: editLabel, variant: 'warning', attributes: { [CONTENT_PREVIEW_ACTION_ATTR]: CONTENT_PREVIEW_ACTIONS.EDIT } })}
            ${renderModalFooterActionButton({ id: saveButtonId, text: saveLabel, variant: 'accent', className: 'u-hidden', ariaHidden: true, attributes: { [CONTENT_PREVIEW_ACTION_ATTR]: CONTENT_PREVIEW_ACTIONS.SAVE } })}
        `
    });

    return createModalElement({
        id: modalId,
        className: 'prompt-view-modal content-preview-modal',
        labelledBy: titleId,
        rootAttributes: { 'data-page-scope': 'core' },
        header,
        body,
        footer
    });
};

const contentPreviewModalDefinition: ModalDefinition = Object.freeze({
    id: CONTENT_PREVIEW_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(CONTENT_PREVIEW_MODAL_ID, CONTENT_PREVIEW_UI_TOKENS.CLOSE),
    createElement: (_options: ModalOpenOptions): HTMLElement => createContentPreviewModalElement()
});

const CONTENT_PREVIEW_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([contentPreviewModalDefinition]);

export { CONTENT_PREVIEW_MODAL_DEFINITIONS };
