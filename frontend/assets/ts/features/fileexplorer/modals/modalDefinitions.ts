/* SoAI - File Explorer modal definitions registered by app bootstrap [frontend/assets/ts/features/fileexplorer/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { FILE_EXPLORER_ACTION_METADATA_COPY } from '@features/fileexplorer/actions.ts';
import { FILE_EXPLORER_METADATA_MODAL_ID } from '@features/fileexplorer/modals/constants.ts';

const fileExplorerMetadataModalDefinition: ModalDefinition = Object.freeze({
    id: FILE_EXPLORER_METADATA_MODAL_ID,
    layout: 'md',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const closeLabel = i18n.t('common.close');
        const copyLabel = i18n.t('fileExplorer.modal.copy');
        return createModalElement({
            id: FILE_EXPLORER_METADATA_MODAL_ID,
            rootAttributes: { 'data-page-scope': 'fileExplorer' },
            header: renderStandardModalHeader({ modalId: FILE_EXPLORER_METADATA_MODAL_ID, title: i18n.t('fileExplorer.modal.metadataTitle'), description: i18n.t('common.modalDescriptions.fileExplorerMetadata'), closeLabel }),
            body: renderModalBody(uiHtml`<div id="${modalUiId(FILE_EXPLORER_METADATA_MODAL_ID, 'body')}" class="file-explorer-metadata-body">${i18n.t('fileExplorer.labels.noMetadata')}</div>`),
            footer: renderSplitModalFooter({
                left: renderModalFooterCloseButton({ modalId: FILE_EXPLORER_METADATA_MODAL_ID, text: closeLabel }),
                right: renderModalFooterActionButton({ text: copyLabel, variant: 'primary', action: FILE_EXPLORER_ACTION_METADATA_COPY })
            })
        });
    }
});

const FILE_EXPLORER_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([fileExplorerMetadataModalDefinition]);

export { FILE_EXPLORER_MODAL_DEFINITIONS };
