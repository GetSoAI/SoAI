/* SoAI - Models download modal markup builders [frontend/assets/ts/features/models/modals/downloadmodal/downloadModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { renderDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderRequiredFieldMarker } from '@core/ui/forms/requiredMarker.ts';
import type { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import { MODELS_DOWNLOAD_MODAL_ID } from '@features/models/modals/constants.ts';

type DownloadModalViewHost = {
    getIconSync: typeof getIconSync;
};

const buildDownloadModalTabs = (): TrustedHtml => {
    const modalId = MODELS_DOWNLOAD_MODAL_ID;
    return uiHtml`
        <div class="tabs-container">
            <div class="tabs-nav-wrapper">
                <nav class="tabs-nav" role="tablist">
                    <button class="tabs-tab is-active" data-tab="download" id="${modalUiId(modalId, 'download-tab')}" type="button" role="tab" aria-selected="true" aria-controls="${modalUiId(modalId, 'download-form')}" aria-label="${uiAttr(i18n.t('models.modal.addModel.tabDownload'))}" data-tooltip="${uiAttr(i18n.t('models.modal.addModel.tabDownload'))}">
                        <span class="tabs-tab-label">${i18n.t('models.modal.addModel.tabDownload')}</span>
                        <span class="tab-notify-badge u-hidden" id="${modalUiId(modalId, 'download-notify')}"></span>
                    </button>
                    <button class="tabs-tab" data-tab="provider" id="${modalUiId(modalId, 'provider-tab')}" type="button" role="tab" aria-selected="false" aria-controls="${modalUiId(modalId, 'provider-form')}" aria-label="${uiAttr(i18n.t('models.modal.addModel.tabProvider'))}" data-tooltip="${uiAttr(i18n.t('models.modal.addModel.tabProvider'))}">
                        <span class="tabs-tab-label">${i18n.t('models.modal.addModel.tabProvider')}</span>
                    </button>
                    <button class="tabs-tab u-hidden" data-tab="manual" id="${modalUiId(modalId, 'manual-tab')}" type="button" role="tab" aria-selected="false" aria-controls="${modalUiId(modalId, 'manual-add-panel')}" aria-hidden="true" tabindex="-1" aria-label="${uiAttr(i18n.t('models.modal.addModel.tabManual'))}" data-tooltip="${uiAttr(i18n.t('models.modal.addModel.tabManual'))}">
                        <span class="tabs-tab-label">${i18n.t('models.modal.addModel.tabManual')}</span>
                    </button>
                </nav>
            </div>
        </div>
    `;
};

const buildDownloadModalBody = (page: DownloadModalViewHost): TrustedHtml => {
    const apiKeyPlaceholder = uiAttr(i18n.t('models.modal.addProvider.apiKeyPlaceholder'));
    const modalId = MODELS_DOWNLOAD_MODAL_ID;
    const providerApiKeyId = modalUiId(modalId, 'provider-api-key');
    const providerApiKeyInput = `<input type="${uiAttr(resolveSecretInputType()).html}" id="${uiAttr(providerApiKeyId).html}" class="form-input secret-input" placeholder="${apiKeyPlaceholder.html}">`;
    const downloadPluginSelectMarkup = renderDropdownSelectControl({
        selectMarkup: `<select id="${modalUiId(modalId, 'download-plugin-select')}" class="form-input"><option value="">${uiText(i18n.t('models.modal.addModel.pluginPlaceholder')).html}</option></select>`
    });
    const providerPluginSelectMarkup = renderDropdownSelectControl({
        selectMarkup: `<select id="${modalUiId(modalId, 'provider-plugin-select')}" class="form-input"><option value="">${uiText(i18n.t('models.modal.addProvider.pluginPlaceholder')).html}</option></select>`
    });

    return uiHtml`
        <div class="download-model-modal-scroll">
            <div id="${modalUiId(modalId, 'operation-progress-list')}" class="ui-operation-progress-list"></div>
            <div id="${modalUiId(modalId, 'download-form')}" class="modal-form-section" role="tabpanel" aria-labelledby="${modalUiId(modalId, 'download-tab')}">
                <div class="form-group">
                    <label for="${modalUiId(modalId, 'download-plugin-select')}">${i18n.t('models.modal.addModel.pluginLabel')} ${renderRequiredFieldMarker({ id: modalUiId(modalId, 'download-plugin-required-marker'), hidden: true })}</label>
                    ${toTrustedUiHtml(downloadPluginSelectMarkup)}
                    <div class="form-help">${i18n.t('models.modal.addModel.pluginHelp')}</div>
                </div>
                <div class="form-group u-hidden model-search-group" id="${modalUiId(modalId, 'model-search-group')}">
                    <label for="${modalUiId(modalId, 'model-search-input')}">${i18n.t('models.modal.addModel.searchLabel')}</label>
                    <div class="form-row-split form-row-split--search">
                        <div class="form-col-main">
                            <div class="searchbar-container searchbar-container--collection">
                                <input type="text" id="${modalUiId(modalId, 'model-search-input')}" class="form-input searchbar-input" placeholder="" autocomplete="off">
                                <span class="searchbar-icon">${page.getIconSync('search', { size: 16, strokeWidth: 1.5 })}</span>
                            </div>
                        </div>
                        <div class="form-col-secondary form-col-action">
                            <button class="ui-button" id="${modalUiId(modalId, 'model-search-button')}" type="button" aria-label="${uiAttr(i18n.t('models.modal.addModel.searchButton'))}" data-tooltip="${uiAttr(i18n.t('models.modal.addModel.searchButton'))}" disabled>${i18n.t('models.modal.addModel.searchButton')}</button>
                        </div>
                    </div>
                    <div class="form-help">${i18n.t('models.modal.addModel.searchHelp')}</div>
                    <div class="u-hidden model-search-results" id="${modalUiId(modalId, 'model-search-results')}"></div>
                </div>
                <div id="${modalUiId(modalId, 'download-plugin-warning')}" class="form-disclaimer u-hidden"></div>
                <div class="form-group u-hidden model-id-group" id="${modalUiId(modalId, 'model-id-group')}">
                    <div class="form-row-split form-row-split--with-action">
                        <div class="form-col-main">
                            <label for="${modalUiId(modalId, 'model-id')}">${i18n.t('models.modal.addModel.modelIdLabel')} ${renderRequiredFieldMarker()}</label>
                            <input type="text" id="${modalUiId(modalId, 'model-id')}" class="form-input">
                        </div>
                        <div class="form-col-secondary">
                            <label for="${modalUiId(modalId, 'model-quant')}">${i18n.t('models.modal.addModel.quantLabel')}</label>
                            <input type="text" id="${modalUiId(modalId, 'model-quant')}" class="form-input">
                        </div>
                        <div class="form-col-secondary form-col-action">
                            <label>&nbsp;</label>
                            <button class="ui-button ui-variant-primary" id="${modalUiId(modalId, 'model-variant-check')}" type="button" aria-label="${uiAttr(i18n.t('models.modal.addModel.variantCheck.button'))}" data-tooltip="${uiAttr(i18n.t('models.modal.addModel.variantCheck.button'))}" disabled>${i18n.t('models.modal.addModel.variantCheck.button')}</button>
                        </div>
                    </div>
                    <div class="form-group u-hidden variant-search-group" id="${modalUiId(modalId, 'variant-search-group')}">
                        <label for="${modalUiId(modalId, 'variant-search-input')}">${i18n.t('models.modal.addModel.variantSearchLabel')}</label>
                        <div class="form-row-split form-row-split--search">
                            <div class="form-col-main">
                                <div class="searchbar-container searchbar-container--collection">
                                    <input type="text" id="${modalUiId(modalId, 'variant-search-input')}" class="form-input searchbar-input" placeholder="${uiAttr(i18n.t('models.modal.addModel.variantSearchPlaceholder'))}" autocomplete="off">
                                    <span class="searchbar-icon">${page.getIconSync('search', { size: 16, strokeWidth: 1.5 })}</span>
                                </div>
                            </div>
                            <div class="form-col-secondary form-col-action">
                                <button class="ui-button" id="${modalUiId(modalId, 'variant-search-button')}" type="button" aria-label="${uiAttr(i18n.t('models.modal.addModel.variantSearchButton'))}" data-tooltip="${uiAttr(i18n.t('models.modal.addModel.variantSearchButton'))}" disabled>${i18n.t('models.modal.addModel.variantSearchButton')}</button>
                            </div>
                        </div>
                        <div class="form-help">${i18n.t('models.modal.addModel.variantSearchHelp')}</div>
                    </div>
                    <div class="form-help">${i18n.t('models.modal.addModel.quantHelp')}</div>
                    <div class="variant-check-status-row">
                        <div class="variant-check-status" id="${modalUiId(modalId, 'model-variant-status')}" aria-live="polite"></div>
                        <div class="variant-check-filter-status" id="${modalUiId(modalId, 'model-variant-filter-status')}" aria-live="polite"></div>
                    </div>
                    <div class="variant-check-results u-hidden" id="${modalUiId(modalId, 'model-variant-results')}"></div>
                </div>
                <div class="form-group u-hidden" id="${modalUiId(modalId, 'repository-link-group')}">
                    <label>${i18n.t('models.modal.addModel.repositoryLabel')}</label>
                    <div class="repository-link-display">
                        <a id="${modalUiId(modalId, 'repository-link')}" href="#" target="_blank" rel="noopener noreferrer" class="repository-link">
                            ${page.getIconSync('external-link', { size: 16, strokeWidth: 1.5 })}<span id="${modalUiId(modalId, 'repository-link-text')}"></span>
                        </a>
                    </div>
                    <div id="${modalUiId(modalId, 'repository-badges-container')}" class="repository-badges-container"></div>
                </div>
            </div>
            <div id="${modalUiId(modalId, 'provider-form')}" class="modal-form-section u-hidden" role="tabpanel" aria-labelledby="${modalUiId(modalId, 'provider-tab')}" aria-hidden="true" hidden>
                <div class="form-group">
                    <label for="${modalUiId(modalId, 'provider-plugin-select')}">${i18n.t('models.modal.addProvider.pluginLabel')} ${renderRequiredFieldMarker({ id: modalUiId(modalId, 'provider-plugin-required-marker'), hidden: true })}</label>
                    ${toTrustedUiHtml(providerPluginSelectMarkup)}
                    <div class="form-help">${i18n.t('models.modal.addProvider.pluginHelp')}</div>
                </div>
                <div class="form-group u-hidden" id="${modalUiId(modalId, 'provider-details-group')}">
                    <label for="${modalUiId(modalId, 'provider-name')}">${i18n.t('models.modal.addProvider.nameLabel')} ${renderRequiredFieldMarker()}</label>
                    <input type="text" id="${modalUiId(modalId, 'provider-name')}" class="form-input">
                    <div class="form-help">${i18n.t('models.modal.addProvider.nameHelp')}</div>
                </div>
                <div class="form-group u-hidden" id="${modalUiId(modalId, 'provider-api-url-group')}">
                    <label for="${modalUiId(modalId, 'provider-api-url')}">${i18n.t('models.modal.addProvider.apiUrlLabel')}</label>
                    <input type="text" id="${modalUiId(modalId, 'provider-api-url')}" class="form-input" placeholder="${uiAttr(i18n.t('models.modal.addProvider.apiUrlPlaceholder'))}">
                    <div class="form-help">${i18n.t('models.modal.addProvider.apiUrlHelp')}</div>
                </div>
                <div class="form-group u-hidden" id="${modalUiId(modalId, 'provider-api-key-group')}">
                    <label for="${uiAttr(providerApiKeyId).html}">${i18n.t('models.modal.addProvider.apiKeyLabel')}</label>
                    ${toTrustedUiHtml(renderSecretInputControl({ inputId: providerApiKeyId, inputMarkup: providerApiKeyInput }))}
                    <div class="form-help">${i18n.t('models.modal.addProvider.apiKeyHelp')}</div>
                </div>
                <div class="form-group u-hidden" id="${modalUiId(modalId, 'provider-models-group')}">
                    <label for="${modalUiId(modalId, 'provider-models-filter')}">${i18n.t('models.modal.addProvider.modelsFilterLabel')}</label>
                    <input type="text" id="${modalUiId(modalId, 'provider-models-filter')}" class="form-input" placeholder="${uiAttr(i18n.t('models.modal.addProvider.modelsFilterPlaceholder'))}">
                    <div class="form-help">${i18n.t('models.modal.addProvider.modelsFilterHelp')}</div>
                </div>
            </div>
            <div id="${modalUiId(modalId, 'manual-add-panel')}" class="modal-form-section u-hidden" role="tabpanel" aria-labelledby="${modalUiId(modalId, 'manual-tab')}" aria-hidden="true" hidden>
                <div class="form-group">
                    <label for="${modalUiId(modalId, 'manual-models-path')}">${i18n.t('models.modal.manualAdd.title')}</label>
                    <div id="${modalUiId(modalId, 'manual-discovery-text')}" class="manual-discovery-text">${i18n.t('models.modal.manualAdd.loading')}</div>
                    <div class="form-row-split manual-path-row">
                        <div class="form-col-main">
                            <input
                                type="text"
                                id="${modalUiId(modalId, 'manual-models-path')}"
                                class="form-input manual-models-path"
                                readonly
                                placeholder="${uiAttr(i18n.t('models.modal.manualAdd.pathPlaceholder'))}"
                            >
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div
            id="${modalUiId(modalId, 'selected-model-display')}"
            class="download-model-selected-model-bar u-hidden"
            aria-hidden="true"
        >
            <span class="download-model-selected-model-label">${i18n.t('models.modal.addModel.selectedLabel')}</span>
            <span class="download-model-selected-model-id"></span>
            <span class="download-model-selected-model-quant"></span>
        </div>
    `;
};

export { buildDownloadModalBody, buildDownloadModalTabs };
