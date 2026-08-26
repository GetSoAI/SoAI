/* SoAI - Download plugin modal definition [frontend/assets/ts/features/plugins/modals/downloadPluginModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';

import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { renderRequiredFieldMarker } from '@core/ui/forms/requiredMarker.ts';
import { PLUGINS_ACTION_DOWNLOAD_CHOOSE_FILE, PLUGINS_ACTION_DOWNLOAD_CONFIRM, PLUGINS_ACTION_DOWNLOAD_FILE_CHANGE, PLUGINS_ACTION_DOWNLOAD_FILE_TAB, PLUGINS_ACTION_DOWNLOAD_MANUAL_COPY_PATH, PLUGINS_ACTION_DOWNLOAD_MANUAL_OPEN_FILE_EXPLORER, PLUGINS_ACTION_DOWNLOAD_MANUAL_RESTART, PLUGINS_ACTION_DOWNLOAD_MANUAL_TAB, PLUGINS_ACTION_DOWNLOAD_URL_INPUT, PLUGINS_ACTION_DOWNLOAD_URL_TAB } from '@features/plugins/contracts/pluginActionIds.ts';

const DOWNLOAD_PLUGIN_MODAL_ID = 'download-plugin-modal';

const createDownloadPluginModalElement = (): HTMLElement => {
    const modalId = DOWNLOAD_PLUGIN_MODAL_ID;
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('plugins.modal.addPlugin.title'),
        description: i18n.t('common.modalDescriptions.pluginsDownload'),
        titleId,
        closeLabel: i18n.t('common.close'),
        sections: uiHtml`
            <div class="tabs-container">
                <div class="tabs-nav-wrapper">
                    <nav class="tabs-nav" role="tablist">
                        <button
                            class="tabs-tab is-active"
                            data-tab="url"
                            data-action="${PLUGINS_ACTION_DOWNLOAD_URL_TAB}"
                            id="${modalUiId(modalId, 'url-tab')}"
                            type="button"
                            role="tab"
                            aria-selected="true"
                            aria-controls="${modalUiId(modalId, 'url-form')}"
                            aria-label="${uiAttr(i18n.t('plugins.modal.addPlugin.tabUrl'))}"
                            data-tooltip="${uiAttr(i18n.t('plugins.modal.addPlugin.tabUrl'))}"
                        >
                            <span class="tabs-tab-label">${i18n.t('plugins.modal.addPlugin.tabUrl')}</span>
                        </button>
                        <button
                            class="tabs-tab"
                            data-tab="file"
                            data-action="${PLUGINS_ACTION_DOWNLOAD_FILE_TAB}"
                            id="${modalUiId(modalId, 'file-tab')}"
                            type="button"
                            role="tab"
                            aria-selected="false"
                            aria-controls="${modalUiId(modalId, 'file-form')}"
                            aria-label="${uiAttr(i18n.t('plugins.modal.addPlugin.tabFile'))}"
                            data-tooltip="${uiAttr(i18n.t('plugins.modal.addPlugin.tabFile'))}"
                        >
                            <span class="tabs-tab-label">${i18n.t('plugins.modal.addPlugin.tabFile')}</span>
                        </button>
                        <button
                            class="tabs-tab u-hidden"
                            data-tab="manual"
                            data-action="${PLUGINS_ACTION_DOWNLOAD_MANUAL_TAB}"
                            id="${modalUiId(modalId, 'manual-tab')}"
                            type="button"
                            role="tab"
                            aria-selected="false"
                            aria-controls="${modalUiId(modalId, 'manual-form')}"
                            aria-hidden="true"
                            tabindex="-1"
                            aria-label="${uiAttr(i18n.t('plugins.modal.addPlugin.tabManual'))}"
                            data-tooltip="${uiAttr(i18n.t('plugins.modal.addPlugin.tabManual'))}"
                        >
                            <span class="tabs-tab-label">${i18n.t('plugins.modal.addPlugin.tabManual')}</span>
                        </button>
                    </nav>
                </div>
            </div>
        `
    });
    const body = renderModalBody(uiHtml`
        <div id="${modalUiId(modalId, 'operation-progress-list')}" class="ui-operation-progress-list"></div>
        <div id="${modalUiId(modalId, 'url-form')}" class="modal-form-section" role="tabpanel" aria-labelledby="${modalUiId(modalId, 'url-tab')}">
            <div class="form-group">
                <label for="${modalUiId(modalId, 'plugin-url')}">
                    ${i18n.t('plugins.modal.addPlugin.urlLabel')}
                    ${renderRequiredFieldMarker()}
                </label>
                <input
                    type="text"
                    data-action="${PLUGINS_ACTION_DOWNLOAD_URL_INPUT}"
                    id="${modalUiId(modalId, 'plugin-url')}"
                    class="form-input"
                    placeholder="${uiAttr(i18n.t('plugins.modal.addPlugin.urlPlaceholder'))}"
                />
                <div class="form-help">${i18n.t('plugins.modal.addPlugin.urlHelp')}</div>
            </div>
            <div id="${modalUiId(modalId, 'url-disclaimer')}" class="form-disclaimer u-hidden">${i18n.t('plugins.modal.addPlugin.securityDisclaimer')}</div>
        </div>
        <div id="${modalUiId(modalId, 'file-form')}" class="modal-form-section u-hidden" role="tabpanel" aria-labelledby="${modalUiId(modalId, 'file-tab')}" aria-hidden="true" hidden>
            <div class="form-group">
                <label for="${modalUiId(modalId, 'plugin-file')}">
                    ${i18n.t('plugins.modal.addPlugin.fileLabel')}
                    ${renderRequiredFieldMarker()}
                </label>
                <div class="plugin-file-input-row">
                    <button
                        class="ui-button"
                        data-action="${PLUGINS_ACTION_DOWNLOAD_CHOOSE_FILE}"
                        id="${modalUiId(modalId, 'choose-file-btn')}"
                        type="button"
                        aria-label="${uiAttr(i18n.t('plugins.modal.addPlugin.chooseFile'))}"
                        data-tooltip="${uiAttr(i18n.t('plugins.modal.addPlugin.chooseFile'))}"
                    >
                        ${i18n.t('plugins.modal.addPlugin.chooseFile')}
                    </button>
                    <span id="${modalUiId(modalId, 'selected-file-name')}" class="plugin-selected-file u-hidden"></span>
                </div>
                <input
                    type="file"
                    data-action="${PLUGINS_ACTION_DOWNLOAD_FILE_CHANGE}"
                    id="${modalUiId(modalId, 'plugin-file')}"
                    class="plugin-file-input"
                    accept=".soaiplugin"
                />
                <div class="form-help">${i18n.t('plugins.modal.addPlugin.fileHelp')}</div>
            </div>
            <div id="${modalUiId(modalId, 'file-disclaimer')}" class="form-disclaimer u-hidden">${i18n.t('plugins.modal.addPlugin.securityDisclaimer')}</div>
        </div>
        <div id="${modalUiId(modalId, 'manual-form')}" class="modal-form-section u-hidden" role="tabpanel" aria-labelledby="${modalUiId(modalId, 'manual-tab')}" aria-hidden="true" hidden>
            <div class="form-group">
                <label for="${modalUiId(modalId, 'manual-plugins-path')}">${i18n.t('plugins.modal.addPlugin.tabManual')}</label>
                <div id="${modalUiId(modalId, 'manual-description')}" class="manual-discovery-text">${i18n.t('plugins.modal.addPlugin.manualLoading')}</div>
                <div class="form-row-split manual-path-row">
                    <div class="form-col-main">
                        <input
                            type="text"
                            id="${modalUiId(modalId, 'manual-plugins-path')}"
                            class="form-input manual-models-path"
                            readonly
                            placeholder="${uiAttr(i18n.t('plugins.modal.addPlugin.manualPathPlaceholder'))}"
                        />
                    </div>
                </div>
            </div>
        </div>
    `);
    const closeText = i18n.t('plugins.modal.addPlugin.close');
    const openFileExplorerText = i18n.t('plugins.modal.addPlugin.manualOpenFileExplorerButton');
    const copyText = i18n.t('common.copy');
    const restartText = i18n.t('plugins.modal.addPlugin.manualRestartButton');
    const confirmText = i18n.t('plugins.modal.addPlugin.confirmDownload');
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: closeText }),
        right: uiHtml`${renderModalFooterActionButton({
            text: openFileExplorerText,
            id: modalUiId(modalId, 'manual-open-file-explorer-btn'),
            variant: 'neutral',
            action: PLUGINS_ACTION_DOWNLOAD_MANUAL_OPEN_FILE_EXPLORER,
            className: 'u-hidden',
            disabled: true
        })}${renderModalFooterActionButton({
            text: copyText,
            id: modalUiId(modalId, 'manual-copy-path'),
            variant: 'primary',
            action: PLUGINS_ACTION_DOWNLOAD_MANUAL_COPY_PATH,
            className: 'u-hidden',
            disabled: true
        })}${renderModalFooterActionButton({
            text: restartText,
            id: modalUiId(modalId, 'manual-power-btn'),
            variant: 'warning',
            action: PLUGINS_ACTION_DOWNLOAD_MANUAL_RESTART,
            className: 'u-hidden',
            disabled: true
        })}${renderModalFooterActionButton({
            text: confirmText,
            id: modalUiId(modalId, 'confirm-download'),
            variant: 'accent',
            action: PLUGINS_ACTION_DOWNLOAD_CONFIRM
        })}`
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

const downloadPluginModalDefinition: ModalDefinition = Object.freeze({
    id: DOWNLOAD_PLUGIN_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(DOWNLOAD_PLUGIN_MODAL_ID, 'plugin-url'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createDownloadPluginModalElement()
});

export { DOWNLOAD_PLUGIN_MODAL_ID, downloadPluginModalDefinition };
