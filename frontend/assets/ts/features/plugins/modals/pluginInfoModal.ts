/* SoAI - Plugin information modal definition [frontend/assets/ts/features/plugins/modals/pluginInfoModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';

import { uiHtml } from '@core/security/uiHtml.ts';
import { PLUGINS_ACTION_INFO_COPY } from '@features/plugins/contracts/pluginActionIds.ts';

const PLUGIN_INFO_MODAL_ID = 'plugin-info-modal';

const createPluginInfoModalElement = (): HTMLElement => {
    const modalId = PLUGIN_INFO_MODAL_ID;
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('plugins.modal.info.title'),
        description: i18n.t('common.modalDescriptions.pluginsInfo'),
        titleId,
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(uiHtml`<div id="${modalUiId(modalId, 'content')}" class="plugin-info-modal-content"></div>`, { className: 'modal-body--sectioned' });
    const closeText = i18n.t('common.close');
    const copyText = i18n.t('plugins.modal.info.copy');
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: closeText }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'copy'), text: copyText, variant: 'primary', action: PLUGINS_ACTION_INFO_COPY })
    });
    return createModalElement({
        id: modalId,
        labelledBy: titleId,
        rootAttributes: { 'data-page-scope': 'plugins' },
        header,
        body,
        footer
    });
};

const pluginInfoModalDefinition: ModalDefinition = Object.freeze({
    id: PLUGIN_INFO_MODAL_ID,
    layout: 'md',
    initialFocusSelector: modalUiSelector(PLUGIN_INFO_MODAL_ID, 'copy'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createPluginInfoModalElement()
});

export { PLUGIN_INFO_MODAL_ID, pluginInfoModalDefinition };
