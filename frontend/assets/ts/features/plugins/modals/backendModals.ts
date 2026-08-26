/* SoAI - Backend install/manage modal definitions [frontend/assets/ts/features/plugins/modals/backendModals.ts] */
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
import { PLUGINS_ACTION_BACKEND_INSTALL_START, PLUGINS_ACTION_BACKEND_UNINSTALL, PLUGINS_ACTION_BACKEND_UPDATE_CHECK } from '@features/plugins/contracts/pluginActionIds.ts';

const MANAGE_BACKEND_MODAL_ID = 'manage-backend-modal';

const renderBackendModalBody = (modalId: string) => {
    return renderModalBody(
        uiHtml`
            <div id="${modalUiId(modalId, 'operation-container')}" class="ui-operation-progress-list backend-operation-container"></div>
            <div id="${modalUiId(modalId, 'plugin-info')}"></div>
            <div id="${modalUiId(modalId, 'warning')}" class="form-disclaimer u-hidden"></div>
            <div id="${modalUiId(modalId, 'version-info')}" class="u-hidden backend-version-info"></div>
        `,
        { className: 'modal-body--sectioned' }
    );
};

const renderBackendModalFooterActions = (modalId: string) => {
    return uiHtml`
        <div id="${modalUiId(modalId, 'variant-selector')}" class="backend-variant-footer-slot"></div>
        ${renderModalFooterActionButton({ text: i18n.t('plugins.modal.installBackend.startInstall'), id: modalUiId(modalId, 'start-install'), action: PLUGINS_ACTION_BACKEND_INSTALL_START, className: 'u-hidden', variant: 'accent' })}
        ${renderModalFooterActionButton({ id: modalUiId(modalId, 'uninstall'), text: i18n.t('plugins.modal.manageBackend.uninstall'), action: PLUGINS_ACTION_BACKEND_UNINSTALL, variant: 'danger' })}
        ${renderModalFooterActionButton({ id: modalUiId(modalId, 'check-update'), text: i18n.t('plugins.modal.manageBackend.checkUpdates'), action: PLUGINS_ACTION_BACKEND_UPDATE_CHECK, variant: 'neutral' })}
    `;
};

const createBackendModalElement = (): HTMLElement => {
    const modalId = MANAGE_BACKEND_MODAL_ID;
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('plugins.modal.manageBackend.title'),
        description: i18n.t('common.modalDescriptions.pluginsManageBackend'),
        titleId,
        closeLabel: i18n.t('common.close')
    });
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('plugins.modal.manageBackend.close') }),
        right: renderBackendModalFooterActions(modalId)
    });
    return createModalElement({
        id: modalId,
        labelledBy: titleId,
        rootAttributes: { 'data-page-scope': 'plugins' },
        header,
        body: renderBackendModalBody(modalId),
        footer
    });
};

const manageBackendModalDefinition: ModalDefinition = Object.freeze({
    id: MANAGE_BACKEND_MODAL_ID,
    layout: 'md',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => createBackendModalElement()
});

export { MANAGE_BACKEND_MODAL_ID, manageBackendModalDefinition };
