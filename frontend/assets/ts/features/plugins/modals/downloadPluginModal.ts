/* SoAI - Download plugin modal definition [frontend/assets/ts/features/plugins/modals/downloadPluginModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderModalTabIntro, renderModalTabPanel, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';

import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { renderRequiredFieldMarker } from '@core/ui/forms/requiredMarker.ts';
import { renderFileDropArea } from '@core/ui/fileDropArea.ts';
import { PLUGINS_ACTION_DOWNLOAD_CHOOSE_FILE, PLUGINS_ACTION_DOWNLOAD_CONFIRM, PLUGINS_ACTION_DOWNLOAD_FILE_CHANGE, PLUGINS_ACTION_DOWNLOAD_FILE_TAB, PLUGINS_ACTION_DOWNLOAD_MANUAL_COPY_PATH, PLUGINS_ACTION_DOWNLOAD_MANUAL_OPEN_FILE_EXPLORER, PLUGINS_ACTION_DOWNLOAD_MANUAL_RESTART, PLUGINS_ACTION_DOWNLOAD_MANUAL_TAB, PLUGINS_ACTION_DOWNLOAD_URL_INPUT, PLUGINS_ACTION_DOWNLOAD_URL_TAB } from '@features/plugins/contracts/pluginActionIds.ts';

const DOWNLOAD_PLUGIN_MODAL_ID = 'download-plugin-modal';
const DOWNLOAD_PLUGIN_INITIAL_FOCUS_SELECTOR = '.ui-modal-tab-panel:not([hidden]) :is(input:not([type="file"]), .ui-file-drop-area)';

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
                         data-modal-localize="aria-label data-tooltip">
                            <span class="tabs-tab-label" data-modal-localize="text">${i18n.t('plugins.modal.addPlugin.tabUrl')}</span>
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
                         data-modal-localize="aria-label data-tooltip">
                            <span class="tabs-tab-label" data-modal-localize="text">${i18n.t('plugins.modal.addPlugin.tabFile')}</span>
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
                         data-modal-localize="aria-label data-tooltip">
                            <span class="tabs-tab-label" data-modal-localize="text">${i18n.t('plugins.modal.addPlugin.tabManual')}</span>
                        </button>
                    </nav>
                </div>
            </div>
        `
    });
    const body = renderModalBody(uiHtml`
        <div id="${modalUiId(modalId, 'operation-progress-list')}" class="ui-operation-progress-list"></div>
        ${renderModalTabPanel({
            id: modalUiId(modalId, 'url-form'),
            labelledBy: modalUiId(modalId, 'url-tab'),
            active: true,
            className: 'modal-form-section',
            content: uiHtml`
                <div class="form-group" data-modal-localize="text">
                    ${renderModalTabIntro({ title: i18n.t('plugins.modal.addPlugin.tabUrl'), description: i18n.t('plugins.modal.addPlugin.urlHelp') })}
                    <label class="visually-hidden" for="${modalUiId(modalId, 'plugin-url')}" data-modal-localize="text">
                        ${i18n.t('plugins.modal.addPlugin.urlLabel')}
                        ${renderRequiredFieldMarker()}
                    </label>
                    <input
                        type="text"
                        data-action="${PLUGINS_ACTION_DOWNLOAD_URL_INPUT}"
                        id="${modalUiId(modalId, 'plugin-url')}"
                        class="form-input"
                        placeholder="${uiAttr(i18n.t('plugins.modal.addPlugin.urlPlaceholder'))}"
                    / data-modal-localize="placeholder">
                </div>
                <div id="${modalUiId(modalId, 'url-disclaimer')}" class="form-disclaimer u-hidden" data-modal-localize="text">${i18n.t('plugins.modal.addPlugin.securityDisclaimer')}</div>
            `
        })}
        ${renderModalTabPanel({
            id: modalUiId(modalId, 'file-form'),
            labelledBy: modalUiId(modalId, 'file-tab'),
            className: 'modal-form-section',
            content: uiHtml`
                <div class="form-group ui-file-drop-form" data-modal-localize="text">
                    ${renderModalTabIntro({ title: i18n.t('plugins.modal.addPlugin.tabFile'), description: i18n.t('plugins.modal.addPlugin.fileHelp') })}
                    <label class="visually-hidden" for="${modalUiId(modalId, 'plugin-file')}" data-modal-localize="text">
                        ${i18n.t('plugins.modal.addPlugin.fileLabel')}
                        ${renderRequiredFieldMarker()}
                    </label>
                    <input
                        type="file"
                        data-action="${PLUGINS_ACTION_DOWNLOAD_FILE_CHANGE}"
                        id="${modalUiId(modalId, 'plugin-file')}"
                        class="plugin-file-input"
                        accept=".soaiplugin"
                    />
                    ${renderFileDropArea({
                        id: modalUiId(modalId, 'file-drop-area'),
                        action: PLUGINS_ACTION_DOWNLOAD_CHOOSE_FILE,
                        title: i18n.t('plugins.modal.addPlugin.fileDropTitle'),
                        hint: i18n.t('plugins.modal.addPlugin.fileDropHint'),
                        icons: ['plugin']
                    })}
                    <span id="${modalUiId(modalId, 'selected-file-name')}" class="plugin-selected-file u-hidden" aria-live="polite"></span>
                    <div class="ui-file-drop-actions">
                        ${renderModalFooterActionButton({
                            text: i18n.t('plugins.modal.addPlugin.confirmUpload'),
                            id: modalUiId(modalId, 'confirm-upload'),
                            variant: 'accent',
                            action: PLUGINS_ACTION_DOWNLOAD_CONFIRM,
                            className: 'ui-file-drop-action-button',
                            disabled: true
                        })}
                    </div>
                </div>
                <div id="${modalUiId(modalId, 'file-disclaimer')}" class="form-disclaimer u-hidden" data-modal-localize="text">${i18n.t('plugins.modal.addPlugin.securityDisclaimer')}</div>
            `
        })}
        ${renderModalTabPanel({
            id: modalUiId(modalId, 'manual-form'),
            labelledBy: modalUiId(modalId, 'manual-tab'),
            className: 'modal-form-section',
            content: uiHtml`
                <div class="form-group">
                    ${renderModalTabIntro({
                        title: i18n.t('plugins.modal.addPlugin.tabManual'),
                        description: i18n.t('plugins.modal.addPlugin.manualLoading'),
                        descriptionId: modalUiId(modalId, 'manual-description')
                    })}
                    <label class="visually-hidden" for="${modalUiId(modalId, 'manual-plugins-path')}" data-modal-localize="text">${i18n.t('plugins.modal.addPlugin.tabManual')}</label>
                    <div class="form-row-split">
                        <div class="form-col-main">
                            <input dir="ltr"
                                type="text"
                                id="${modalUiId(modalId, 'manual-plugins-path')}"
                                class="form-input ui-modal-manual-path-input"
                                readonly
                                placeholder="${uiAttr(i18n.t('plugins.modal.addPlugin.manualPathPlaceholder'))}"
                            / data-modal-localize="placeholder">
                        </div>
                    </div>
                </div>
            `
        })}
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
    initialFocusSelector: DOWNLOAD_PLUGIN_INITIAL_FOCUS_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => createDownloadPluginModalElement()
});

export { DOWNLOAD_PLUGIN_MODAL_ID, downloadPluginModalDefinition };
