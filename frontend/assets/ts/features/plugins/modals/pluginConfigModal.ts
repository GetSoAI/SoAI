/* SoAI - Plugin configuration modal definition [frontend/assets/ts/features/plugins/modals/pluginConfigModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';

import { uiHtml } from '@core/security/uiHtml.ts';
import { PLUGINS_ACTION_CONFIG_SAVE } from '@features/plugins/contracts/pluginActionIds.ts';

const PLUGIN_CONFIG_MODAL_ID = 'plugin-config-modal';

const createPluginConfigModalElement = (): HTMLElement => {
    const modalId = PLUGIN_CONFIG_MODAL_ID;
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('plugins.modal.config.title'),
        description: i18n.t('common.modalDescriptions.pluginsConfig'),
        titleId,
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(uiHtml`
        <div class="form-group">
            <label id="${modalUiId(modalId, 'content-title')}"></label>
            <div class="form-help">${i18n.t('plugins.modal.config.instructions')}</div>
            <div id="${modalUiId(modalId, 'meta')}" class="plugin-config-meta"></div>
        </div>
        <div id="${modalUiId(modalId, 'form')}"></div>
    `);
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('plugins.modal.config.close') }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'save'), text: i18n.t('plugins.modal.config.save'), action: PLUGINS_ACTION_CONFIG_SAVE, disabled: true, variant: 'accent' })
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

const pluginConfigModalDefinition: ModalDefinition = Object.freeze({
    id: PLUGIN_CONFIG_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => createPluginConfigModalElement()
});

export { PLUGIN_CONFIG_MODAL_ID, pluginConfigModalDefinition };
