/* SoAI - Clone plugin modal definition [frontend/assets/ts/features/plugins/modals/clonePluginModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';

import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { PLUGINS_ACTION_CLONE_START } from '@features/plugins/contracts/pluginActionIds.ts';

const CLONE_PLUGIN_MODAL_ID = 'clone-plugin-modal';

const createClonePluginModalElement = (): HTMLElement => {
    const modalId = CLONE_PLUGIN_MODAL_ID;
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('plugins.modal.clonePlugin.title'),
        description: i18n.t('common.modalDescriptions.pluginsClone'),
        titleId,
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(
        uiHtml`
            <div id="${modalUiId(modalId, 'progress-container')}" class="ui-operation-progress-list clone-progress-container"></div>
            <div id="${modalUiId(modalId, 'plugin-info')}"></div>
            <div id="${modalUiId(modalId, 'name-input-container')}" class="plugin-clone-name-input u-hidden">
                <input
                    type="text"
                    id="${modalUiId(modalId, 'name-input')}"
                    class="form-input"
                    placeholder="${uiAttr(i18n.t('plugins.modal.clonePlugin.namePlaceholder'))}"
                />
            </div>
        `,
        { className: 'modal-body--sectioned' }
    );
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('plugins.modal.clonePlugin.close') }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'start'), text: i18n.t('plugins.modal.clonePlugin.clone'), action: PLUGINS_ACTION_CLONE_START, variant: 'warning' })
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

const clonePluginModalDefinition: ModalDefinition = Object.freeze({
    id: CLONE_PLUGIN_MODAL_ID,
    layout: 'md',
    initialFocusSelector: modalUiSelector(CLONE_PLUGIN_MODAL_ID, 'start'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createClonePluginModalElement()
});

export { CLONE_PLUGIN_MODAL_ID, clonePluginModalDefinition };
