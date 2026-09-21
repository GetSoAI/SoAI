/* SoAI - Models modal definitions registered by app bootstrap [frontend/assets/ts/features/models/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { MODELS_ACTION_ADD_PROVIDER } from '@core/models/pageActions.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';

import { uiHtml, uiText } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { buildDownloadModalBody, buildDownloadModalTabs } from '@features/models/modals/downloadmodal/downloadModalMarkup.ts';
import { buildEditModelModalBody, buildProvidersModalBody, buildRenameModelModalBody, buildVirtualModelsBody, buildVirtualModelsTabs } from '@features/models/modals/markup.ts';
import { buildConstituentPickerMarkup } from '@features/models/modals/virtualmodelsmodal/constituentpicker/markup.ts';
import { EDIT_MODEL_MODAL_ACTION_SAVE, MODELS_DOWNLOAD_MODAL_ID, MODELS_EDIT_MODEL_MODAL_ID, MODELS_PROVIDERS_MODAL_ID, MODELS_RENAME_MODEL_MODAL_ID, MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, MODELS_VIRTUAL_MODELS_MODAL_ID } from '@features/models/modals/constants.ts';

const buildVirtualModelEditModalBody = (): ReturnType<typeof uiHtml> => {
    const modalId = MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID;
    return uiHtml`
        <div id="${modalUiId(modalId, 'vm-edit-summary')}" class="form-help vm-edit-modal-summary"></div>
        <div class="form-group setting-change-surface" id="${modalUiId(modalId, 'vm-edit-strategy-field')}">
            <label for="${modalUiId(modalId, 'vm-edit-strategy')}">${i18n.t('models.modal.virtualModels.strategy')}</label>
            ${toTrustedUiHtml(
                renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'vm-edit-strategy')}" class="form-input">
                <option value="load_balancing">${uiText(i18n.t('models.strategies.load_balancing')).html}</option>
                <option value="failover">${uiText(i18n.t('models.strategies.failover')).html}</option>
            </select>`)
            )}
        </div>
        <div class="form-group setting-change-surface setting-change-surface--child-selection" id="${modalUiId(modalId, 'vm-edit-models-field')}">
            <label>${i18n.t('models.modal.virtualModels.constituentModels')}</label>
            ${buildConstituentPickerMarkup({ modalId, token: 'vm-edit-models' })}
        </div>
    `;
};

const createDownloadModelModalElement = (): HTMLElement => {
    const modalId = MODELS_DOWNLOAD_MODAL_ID;
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('models.modal.addModel.title'),
        description: i18n.t('common.modalDescriptions.modelsDownload'),
        closeLabel: i18n.t('common.close'),
        sections: buildDownloadModalTabs()
    });
    const body = renderModalBody(buildDownloadModalBody({ getIconSync }), { className: 'modal-body--sectioned' });
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('models.modal.addModel.close') }),
        right: uiHtml`
            ${renderModalFooterCloseButton({
                modalId,
                id: modalUiId(modalId, 'download-model-background-btn'),
                text: i18n.t('common.background'),
                className: 'u-hidden'
            })}
            ${renderModalFooterActionButton({
                id: modalUiId(modalId, 'manual-open-file-explorer'),
                text: i18n.t('models.modal.manualAdd.openFileExplorerButton'),
                variant: 'neutral',
                className: 'u-hidden',
                disabled: true
            })}
            ${renderModalFooterActionButton({
                id: modalUiId(modalId, 'manual-copy-path'),
                text: i18n.t('models.modal.manualAdd.copyButton'),
                variant: 'primary',
                className: 'u-hidden',
                disabled: true
            })}
            ${renderModalFooterActionButton({
                id: modalUiId(modalId, 'manual-discovery-button'),
                text: i18n.t('models.modal.manualAdd.discoverButton'),
                variant: 'accent',
                className: 'u-hidden',
                disabled: true
            })}
            ${renderModalFooterActionButton({
                id: modalUiId(modalId, 'confirm-download'),
                text: i18n.t('models.modal.addModel.confirmDownload'),
                variant: 'accent'
            })}
        `
    });
    return createModalElement({
        id: modalId,
        rootAttributes: { 'data-page-scope': 'models' },
        header,
        body,
        footer
    });
};

const createEditModelModalElement = (): HTMLElement => {
    const modalId = MODELS_EDIT_MODEL_MODAL_ID;
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('models.modal.edit.title'),
        description: i18n.t('common.modalDescriptions.modelsEdit'),
        titleId: modalUiId(modalId, 'title'),
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(buildEditModelModalBody(), { className: 'model-edit-body' });
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.close') }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'save'), action: EDIT_MODEL_MODAL_ACTION_SAVE, text: i18n.t('common.save'), variant: 'accent', disabled: true })
    });
    return createModalElement({
        id: modalId,
        labelledBy: modalUiId(modalId, 'title'),
        rootAttributes: { 'data-page-scope': 'models' },
        header,
        body,
        footer
    });
};

const createRenameModelModalElement = (): HTMLElement => {
    const modalId = MODELS_RENAME_MODEL_MODAL_ID;
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('models.modal.rename.title'),
        description: i18n.t('common.modalDescriptions.modelsRename'),
        titleId: modalUiId(modalId, 'title'),
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(buildRenameModelModalBody(), { className: 'model-rename-body' });
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.cancel') }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'save'), text: i18n.t('common.save'), variant: 'accent', className: 'model-rename-save' })
    });
    return createModalElement({
        id: modalId,
        labelledBy: modalUiId(modalId, 'title'),
        rootAttributes: { 'data-page-scope': 'models' },
        header,
        body,
        footer
    });
};

const createProvidersModalElement = (): HTMLElement => {
    const modalId = MODELS_PROVIDERS_MODAL_ID;
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('models.modal.providers.title'),
        description: i18n.t('common.modalDescriptions.modelsProviders'),
        titleId: modalUiId(modalId, 'title'),
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(buildProvidersModalBody());
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('models.modal.providers.close') }),
        right: renderModalFooterActionButton({
            id: modalUiId(modalId, 'provider-add'),
            text: i18n.t('models.modal.providers.addProvider'),
            action: MODELS_ACTION_ADD_PROVIDER,
            variant: 'accent'
        })
    });
    return createModalElement({
        id: modalId,
        labelledBy: modalUiId(modalId, 'title'),
        rootAttributes: { 'data-page-scope': 'models' },
        header,
        body,
        footer
    });
};

const createVirtualModelsModalElement = (): HTMLElement => {
    const modalId = MODELS_VIRTUAL_MODELS_MODAL_ID;
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('models.modal.virtualModels.title'),
        description: i18n.t('common.modalDescriptions.modelsVirtual'),
        titleId: modalUiId(modalId, 'title'),
        closeLabel: i18n.t('common.close'),
        sections: buildVirtualModelsTabs()
    });
    const body = renderModalBody(buildVirtualModelsBody());
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.close') }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'vm-save-create'), text: i18n.t('models.actions.createVirtualModel'), variant: 'accent' })
    });
    return createModalElement({
        id: modalId,
        labelledBy: modalUiId(modalId, 'title'),
        rootAttributes: { 'data-page-scope': 'models' },
        header,
        body,
        footer
    });
};

const createVirtualModelEditModalElement = (): HTMLElement => {
    const modalId = MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID;
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('models.modal.virtualModels.editTitle'),
        description: i18n.t('common.modalDescriptions.modelsVirtualEdit'),
        titleId: modalUiId(modalId, 'title'),
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(buildVirtualModelEditModalBody());
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.cancel') }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'vm-save-edit'), text: i18n.t('common.save'), variant: 'accent', disabled: true })
    });
    return createModalElement({
        id: modalId,
        labelledBy: modalUiId(modalId, 'title'),
        rootAttributes: { 'data-page-scope': 'models' },
        header,
        body,
        footer
    });
};

const MODELS_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([
    {
        id: MODELS_DOWNLOAD_MODAL_ID,
        layout: 'xl',
        initialFocusSelector: modalUiSelector(MODELS_DOWNLOAD_MODAL_ID, 'download-plugin-select'),
        createElement: (_options: ModalOpenOptions): HTMLElement => createDownloadModelModalElement()
    },
    {
        id: MODELS_EDIT_MODEL_MODAL_ID,
        layout: 'xl',
        initialFocusSelector: modalUiSelector(MODELS_EDIT_MODEL_MODAL_ID, 'view-model-info'),
        createElement: (_options: ModalOpenOptions): HTMLElement => createEditModelModalElement()
    },
    {
        id: MODELS_RENAME_MODEL_MODAL_ID,
        layout: 'md',
        initialFocusSelector: modalUiSelector(MODELS_RENAME_MODEL_MODAL_ID, 'alias-input'),
        createElement: (_options: ModalOpenOptions): HTMLElement => createRenameModelModalElement()
    },
    {
        id: MODELS_PROVIDERS_MODAL_ID,
        layout: 'xl',
        initialFocusSelector: modalUiSelector(MODELS_PROVIDERS_MODAL_ID, 'provider-add'),
        createElement: (_options: ModalOpenOptions): HTMLElement => createProvidersModalElement()
    },
    {
        id: MODELS_VIRTUAL_MODELS_MODAL_ID,
        layout: 'xl',
        initialFocusSelector: modalUiSelector(MODELS_VIRTUAL_MODELS_MODAL_ID, 'vm-name'),
        createElement: (_options: ModalOpenOptions): HTMLElement => createVirtualModelsModalElement()
    },
    {
        id: MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID,
        layout: 'md',
        initialFocusSelector: modalUiSelector(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, 'vm-edit-strategy'),
        createElement: (_options: ModalOpenOptions): HTMLElement => createVirtualModelEditModalElement()
    }
]);

export { MODELS_MODAL_DEFINITIONS };
