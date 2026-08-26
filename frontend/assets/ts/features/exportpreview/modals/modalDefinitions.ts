/* SoAI - Shared export preview modal definitions [frontend/assets/ts/features/exportpreview/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderModalLoadingState, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { EXPORT_PREVIEW_ACTION_DOWNLOAD, EXPORT_PREVIEW_MODAL_ID } from '@features/exportpreview/modals/constants.ts';

const createExportPreviewModalElement = (): HTMLElement => {
    const modalId = EXPORT_PREVIEW_MODAL_ID;
    const closeAriaLabel = i18n.t('common.exportPreview.ariaLabels.close');
    const downloadAriaLabel = i18n.t('common.exportPreview.ariaLabels.download');
    const closeText = i18n.t('common.exportPreview.close');
    const downloadText = i18n.t('common.exportPreview.download');
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('common.exportPreview.title'),
        description: i18n.t('common.modalDescriptions.exportPreview'),
        titleId,
        closeLabel: closeAriaLabel,
        leading: uiHtml`<div class="prompt-modal-header"><div class="prompt-modal-header-left">`,
        trailing: uiHtml`</div></div>`
    });
    const body = renderModalBody(
        uiHtml`
            ${renderModalLoadingState({ text: i18n.t('common.exportPreview.generating'), hidden: true, overlay: true, className: 'content-loading' })}
            <div class="prompt-modal-content">
                <div class="prompt-modal-content-editor">
                    <div class="prompt-modal-content-text prompt-view-text" id="${modalUiId(modalId, 'content')}"></div>
                </div>
            </div>
        `,
        { className: 'modal-body--relative' }
    );
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, id: modalUiId(modalId, 'close'), text: closeText, ariaLabel: closeAriaLabel }),
        right: renderModalFooterActionButton({ text: downloadText, ariaLabel: downloadAriaLabel, id: modalUiId(modalId, 'download'), variant: 'accent', action: EXPORT_PREVIEW_ACTION_DOWNLOAD, disabled: true })
    });
    return createModalElement({
        id: modalId,
        className: 'prompt-view-modal',
        labelledBy: titleId,
        rootAttributes: { 'data-page-scope': 'hardware' },
        header,
        body,
        footer
    });
};

const EXPORT_PREVIEW_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([
    {
        id: EXPORT_PREVIEW_MODAL_ID,
        layout: 'xl',
        initialFocusSelector: modalUiSelector(EXPORT_PREVIEW_MODAL_ID, 'close'),
        createElement: (_options: ModalOpenOptions): HTMLElement => createExportPreviewModalElement()
    }
]);

export { EXPORT_PREVIEW_MODAL_DEFINITIONS };
