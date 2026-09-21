/* SoAI - Models modal markup builders [frontend/assets/ts/features/models/modals/markup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderRequiredFieldMarker } from '@core/ui/forms/requiredMarker.ts';

import { EDIT_MODEL_MODAL_ACTION_COPY_SOURCE, EDIT_MODEL_MODAL_ACTION_DELETE, EDIT_MODEL_MODAL_ACTION_EDIT_PARAMETERS, EDIT_MODEL_MODAL_ACTION_RENAME, EDIT_MODEL_MODAL_ACTION_TEST_MODEL, EDIT_MODEL_MODAL_ACTION_TOGGLE_ENABLED, EDIT_MODEL_MODAL_ACTION_VIEW_INFO, MODELS_EDIT_MODEL_MODAL_ID, MODELS_PROVIDERS_MODAL_ID, MODELS_RENAME_MODEL_MODAL_ID, MODELS_VIRTUAL_MODELS_MODAL_ID, VIRTUAL_MODELS_MODAL_ACTION_CREATE_TAB, VIRTUAL_MODELS_MODAL_ACTION_LIST_TAB } from '@features/models/modals/constants.ts';
import { buildConstituentPickerMarkup } from '@features/models/modals/virtualmodelsmodal/constituentpicker/markup.ts';

const buildEditModelModalBody = (): TrustedHtml => {
    const modalId = MODELS_EDIT_MODEL_MODAL_ID;
    return uiHtml`
        <div class="model-edit-panel">
            <div class="model-edit-field">
                <span class="model-edit-label">${i18n.t('models.modal.edit.actionsLabel')}</span>
                <div class="model-edit-actions">
                    <button type="button" class="ui-button ui-variant-neutral model-edit-action model-edit-action--info" id="${modalUiId(modalId, 'view-model-info')}" data-action="${uiAttr(EDIT_MODEL_MODAL_ACTION_VIEW_INFO)}" aria-label="${uiAttr(i18n.t('models.modal.edit.viewInfo'))}" data-tooltip="${uiAttr(i18n.t('models.modal.edit.viewInfo'))}">
                        <span>${i18n.t('models.modal.edit.viewInfo')}</span>
                    </button>
                    <button type="button" class="ui-button ui-variant-neutral model-edit-action model-edit-action--rename" id="${modalUiId(modalId, 'rename-model')}" data-action="${uiAttr(EDIT_MODEL_MODAL_ACTION_RENAME)}" aria-label="${uiAttr(i18n.t('models.modal.edit.renameModel'))}" data-tooltip="${uiAttr(i18n.t('models.modal.edit.renameModel'))}">
                        <span>${i18n.t('models.modal.edit.renameModel')}</span>
                    </button>
                    <button type="button" class="ui-button ui-variant-primary model-edit-action model-edit-action--test" id="${modalUiId(modalId, 'test-model')}" data-action="${uiAttr(EDIT_MODEL_MODAL_ACTION_TEST_MODEL)}" aria-label="${uiAttr(i18n.t('models.modal.edit.testModel'))}" data-tooltip="${uiAttr(i18n.t('models.modal.edit.testModel'))}">
                        <span>${i18n.t('models.modal.edit.testModel')}</span>
                    </button>
                    <button type="button" class="ui-button ui-variant-warning model-edit-action model-edit-action--parameters" id="${modalUiId(modalId, 'edit-parameters')}" data-action="${uiAttr(EDIT_MODEL_MODAL_ACTION_EDIT_PARAMETERS)}" aria-label="${uiAttr(i18n.t('models.modal.edit.editParameters'))}" data-tooltip="${uiAttr(i18n.t('models.modal.edit.editParameters'))}">
                        <span>${i18n.t('models.modal.edit.editParameters')}</span>
                    </button>
                    <button type="button" class="ui-button ui-variant-primary model-edit-action model-edit-action--copy model-edit-source-copy-mobile" id="${modalUiId(modalId, 'copy-source-id-mobile')}" data-action="${uiAttr(EDIT_MODEL_MODAL_ACTION_COPY_SOURCE)}" aria-label="${uiAttr(i18n.t('models.modal.edit.copyName'))}" data-tooltip="${uiAttr(i18n.t('models.modal.edit.copyName'))}">
                        <span>${i18n.t('models.modal.edit.copyName')}</span>
                    </button>
                    <button type="button" class="ui-button ui-variant-danger model-edit-action model-edit-action--delete" id="${modalUiId(modalId, 'delete-model')}" data-action="${uiAttr(EDIT_MODEL_MODAL_ACTION_DELETE)}" aria-label="${uiAttr(i18n.t('models.modal.edit.deleteModel'))}" data-tooltip="${uiAttr(i18n.t('models.modal.edit.deleteModel'))}">
                        <span>${i18n.t('models.modal.edit.deleteModel')}</span>
                    </button>
                </div>
            </div>
            <div class="model-edit-field">
                <span class="model-edit-label">${i18n.t('models.modal.edit.sourceModelIdLabel')}</span>
                <div class="model-edit-source-row">
                    <div id="${modalUiId(modalId, 'source-model-id')}" class="model-edit-source-value"></div>
                    <button type="button" class="ui-button ui-variant-primary model-edit-action model-edit-action--copy model-edit-source-copy" id="${modalUiId(modalId, 'copy-source-id')}" data-action="${uiAttr(EDIT_MODEL_MODAL_ACTION_COPY_SOURCE)}" aria-label="${uiAttr(i18n.t('models.modal.edit.copyName'))}" data-tooltip="${uiAttr(i18n.t('models.modal.edit.copyName'))}">
                        <span>${i18n.t('models.modal.edit.copyName')}</span>
                    </button>
                </div>
            </div>
            <div class="model-edit-field model-edit-enabled-field setting-change-surface" id="${modalUiId(modalId, 'enabled-field')}">
                <span class="model-edit-label">${i18n.t('models.modal.edit.availabilityLabel')}</span>
                <div class="model-edit-enabled-row ui-collection-card__horizontal plugin-logo-name">
                    <label class="model-edit-enabled-toggle ui-collection-card__toggle toggle-switch plugin-enable-toggle" id="${modalUiId(modalId, 'enabled-toggle')}" data-action="${uiAttr(EDIT_MODEL_MODAL_ACTION_TOGGLE_ENABLED)}">
                        <input type="checkbox" id="${modalUiId(modalId, 'enabled-checkbox')}" aria-label="${uiAttr(i18n.t('common.enabled'))}">
                        <span class="slider"></span>
                        <span class="plugin-enable-label ui-collection-card__toggle-label toggle-label">${i18n.t('common.enabled')}</span>
                    </label>
                    <span class="model-edit-enabled-state" id="${modalUiId(modalId, 'enabled-state')}"></span>
                </div>
                <div class="form-help model-edit-enabled-help">${i18n.t('models.modal.edit.enabledHelp')}</div>
            </div>
            <div class="model-edit-field" id="${modalUiId(modalId, 'capabilities-field')}">
                <span class="model-edit-label">${i18n.t('models.modal.edit.capabilitiesLabel')}</span>
                <div class="model-edit-capabilities" id="${modalUiId(modalId, 'capabilities')}"></div>
            </div>
        </div>
    `;
};

const buildRenameModelModalBody = (): TrustedHtml => {
    const modalId = MODELS_RENAME_MODEL_MODAL_ID;
    return uiHtml`
        <div class="model-rename-form">
            <div class="model-rename-source">
                <span class="model-rename-source-label">${i18n.t('models.modal.rename.sourceModelIdLabel')}</span>
                <div id="${modalUiId(modalId, 'source-model-id')}" class="model-rename-source-value"></div>
            </div>
            <div class="form-group setting-change-surface" id="${modalUiId(modalId, 'alias-field')}">
                <label for="${modalUiId(modalId, 'alias-input')}">${i18n.t('models.modal.rename.aliasLabel')}</label>
                <input type="text" id="${modalUiId(modalId, 'alias-input')}" class="form-input model-rename-input" placeholder="${uiAttr(i18n.t('models.modal.rename.aliasPlaceholder'))}">
                <div class="form-help">${i18n.t('models.modal.rename.aliasHelp')}</div>
            </div>
        </div>
    `;
};

const buildProvidersModalBody = (): TrustedHtml => {
    const modalId = MODELS_PROVIDERS_MODAL_ID;
    return uiHtml`
        <div id="${modalUiId(modalId, 'providers-list')}" class="providers-list"></div>
    `;
};

const buildVirtualModelsTabs = (): TrustedHtml => {
    const modalId = MODELS_VIRTUAL_MODELS_MODAL_ID;
    return uiHtml`
        <div class="tabs-container">
            <div class="tabs-nav-wrapper">
                <nav class="tabs-nav" role="tablist">
                    <button class="tabs-tab is-active" data-tab="vm-create" data-action="${uiAttr(VIRTUAL_MODELS_MODAL_ACTION_CREATE_TAB)}" id="${modalUiId(modalId, 'vm-tab-create')}" type="button" role="tab" aria-selected="true" aria-controls="${modalUiId(modalId, 'vm-form-create')}" aria-label="${uiAttr(i18n.t('models.modal.virtualModels.createTitle'))}" data-tooltip="${uiAttr(i18n.t('models.modal.virtualModels.createTitle'))}">
                        <span class="tabs-tab-label">${i18n.t('models.modal.virtualModels.createTitle')}</span>
                    </button>
                    <button class="tabs-tab" data-tab="vm-list" data-action="${uiAttr(VIRTUAL_MODELS_MODAL_ACTION_LIST_TAB)}" id="${modalUiId(modalId, 'vm-tab-list')}" type="button" role="tab" aria-selected="false" aria-controls="${modalUiId(modalId, 'vm-list')}" aria-label="${uiAttr(i18n.t('models.actions.manageVirtualModels'))}" data-tooltip="${uiAttr(i18n.t('models.actions.manageVirtualModels'))}">
                        <span class="tabs-tab-label">${i18n.t('models.actions.manageVirtualModels')}</span>
                    </button>
                </nav>
            </div>
        </div>
    `;
};

const buildVirtualModelsBody = (): TrustedHtml => {
    const modalId = MODELS_VIRTUAL_MODELS_MODAL_ID;
    const constituentPicker = buildConstituentPickerMarkup({ modalId, token: 'vm-models' });
    return uiHtml`
        <div id="${modalUiId(modalId, 'vm-form-create')}" class="modal-form-section" role="tabpanel" aria-labelledby="${modalUiId(modalId, 'vm-tab-create')}">
            <div class="form-group setting-change-surface" id="${modalUiId(modalId, 'vm-name-field')}">
                <label for="${modalUiId(modalId, 'vm-name')}">${i18n.t('models.modal.virtualModels.name')} ${renderRequiredFieldMarker()}</label>
                <input type="text" id="${modalUiId(modalId, 'vm-name')}" class="form-input" placeholder="${uiAttr(i18n.t('models.modal.virtualModels.namePlaceholder'))}">
            </div>
            <div class="form-group setting-change-surface" id="${modalUiId(modalId, 'vm-strategy-field')}">
                <label for="${modalUiId(modalId, 'vm-strategy')}">${i18n.t('models.modal.virtualModels.strategy')}</label>
                ${toTrustedUiHtml(
                    renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'vm-strategy')}" class="form-input">
                    <option value="load_balancing">${uiText(i18n.t('models.strategies.load_balancing')).html}</option>
                    <option value="failover">${uiText(i18n.t('models.strategies.failover')).html}</option>
                </select>`)
                )}
                <div class="form-help">${i18n.t('models.modal.virtualModels.strategyHelp')}</div>
            </div>
            <div class="form-group setting-change-surface setting-change-surface--child-selection" id="${modalUiId(modalId, 'vm-models-field')}">
                <label>${i18n.t('models.modal.virtualModels.constituentModels')}</label>
                ${constituentPicker}
            </div>
        </div>
            <div id="${modalUiId(modalId, 'vm-list')}" class="modal-form-section u-hidden" role="tabpanel" aria-labelledby="${modalUiId(modalId, 'vm-tab-list')}" aria-hidden="true" hidden>
                <div id="${modalUiId(modalId, 'virtual-models-list')}" class="providers-list"></div>
            </div>
    `;
};

export { buildEditModelModalBody, buildProvidersModalBody, buildRenameModelModalBody, buildVirtualModelsBody, buildVirtualModelsTabs };
