/* SoAI - Model detail modal markup [frontend/assets/ts/features/modeldetail/modals/markup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { renderModalBody, renderModalScaffoldMarkup, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { renderLabelAttributes, toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { ACTION_TEST_COPY_LOGS, ACTION_TEST_LONG, ACTION_TEST_RESET, ACTION_TEST_SHORT, ACTION_TEST_STOP_PLUGIN, ACTION_TEST_TOGGLE_LOGS } from '@features/modeldetail/actions.ts';
import { MODEL_DETAIL_TEST_MODAL_ID } from '@features/modeldetail/modals/constants.ts';

const renderTestModal = (): TrustedHtml => {
    const shortLabel = i18n.t('modelDetail.modal.test.shortTest');
    const shortAria = i18n.t('modelDetail.modal.test.shortTestAriaLabel');
    const longLabel = i18n.t('modelDetail.modal.test.longTest');
    const longAria = i18n.t('modelDetail.modal.test.longTestAriaLabel');
    const toggleLogsAria = i18n.t('modelDetail.modal.test.toggleLogsAriaLabel');
    const placeholderValue = i18n.t('common.notAvailableShort');
    const modalId = MODEL_DETAIL_TEST_MODAL_ID;
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('modelDetail.modal.test.titlePlaceholder'),
        description: i18n.t('common.modalDescriptions.modelDetailTest'),
        titleId,
        closeLabel: i18n.t('common.close'),
        headerClassName: 'modal-header--with-border'
    });
    const body = renderModalBody(
        toTrustedHtml(
            `<div class="model-test-result-row" id="${modalUiId(modalId, 'result')}"><span class="model-test-result-text-only" id="${modalUiId(modalId, 'result-badge')}"><span id="${modalUiId(modalId, 'result-text')}">${i18n.t('modelDetail.modal.test.ready')}</span></span></div>` +
                `<div class="model-test-status-block"><div class="model-test-plugin-status-row"><div class="stat-label">${i18n.t('modelDetail.modal.test.plugin_status')}</div><div class="stat-value"><span class="ui-status-badge plugin-status-badge" id="${modalUiId(modalId, 'plugin-status')}"><span class="status-indicator" id="${modalUiId(modalId, 'plugin-status-led')}"></span><span id="${modalUiId(modalId, 'plugin-status-text')}">${placeholderValue}</span></span></div></div>` +
                `<div class="model-test-model-status-row"><div class="stat-label">${i18n.t('modelDetail.modal.test.modelStatus')}</div><div class="stat-value"><span class="ui-status-badge plugin-status-badge" id="${modalUiId(modalId, 'model-loaded')}"><span class="status-indicator" id="${modalUiId(modalId, 'model-status-led')}"></span><span id="${modalUiId(modalId, 'model-status-text')}">${placeholderValue}</span></span></div></div>` +
                `<div class="model-test-timing-row u-hidden" id="${modalUiId(modalId, 'timing-row')}"><span class="stat-label">${i18n.t('modelDetail.modal.test.elapsedTime')}</span><span class="model-test-elapsed-value" id="${modalUiId(modalId, 'elapsed-time')}">0.0s</span><span class="spinner model-test-elapsed-spinner u-hidden" id="${modalUiId(modalId, 'elapsed-spinner')}"></span></div>` +
                `<div class="model-test-controls-row"><button class="ui-button ui-button--sm ui-variant-danger" type="button" id="${modalUiId(modalId, 'stop-plugin')}" data-action="${ACTION_TEST_STOP_PLUGIN}" ${renderLabelAttributes(i18n.t('modelDetail.modal.test.stopPlugin'))}>${i18n.t('modelDetail.modal.test.stopPlugin')}</button>` +
                `<button class="ui-button ui-button--sm ui-variant-danger" type="button" id="${modalUiId(modalId, 'reset')}" data-action="${ACTION_TEST_RESET}" ${renderLabelAttributes(i18n.t('modelDetail.modal.test.reset'))}>${i18n.t('modelDetail.modal.test.reset')}</button>` +
                `<button class="ui-button ui-button--sm u-hidden" type="button" id="${modalUiId(modalId, 'toggle-logs')}" data-action="${ACTION_TEST_TOGGLE_LOGS}" ${renderLabelAttributes(i18n.t('modelDetail.modal.test.showLogs'))}>${i18n.t('modelDetail.modal.test.showLogs')}</button></div></div>` +
                `<div class="model-test-request-details u-hidden" id="${modalUiId(modalId, 'request-details')}"><div class="model-test-request-grid"><div class="stat-row"><span class="stat-label">${i18n.t('modelDetail.modal.test.requestModelLabel')}</span><span class="stat-value" id="${modalUiId(modalId, 'request-model')}"></span></div>` +
                `<div class="stat-row"><span class="stat-label">${i18n.t('modelDetail.modal.test.requestModeLabel')}</span><span class="stat-value" id="${modalUiId(modalId, 'request-mode')}"></span></div>` +
                `<div class="stat-row"><span class="stat-label">${i18n.t('modelDetail.modal.test.requestStartedLabel')}</span><span class="stat-value" id="${modalUiId(modalId, 'request-started')}"></span></div>` +
                `<div class="stat-row"><span class="stat-label">${i18n.t('modelDetail.modal.test.requestCompletedLabel')}</span><span class="stat-value" id="${modalUiId(modalId, 'request-completed')}"></span></div></div>` +
                `<div class="model-test-request-prompt"><span class="stat-label">${i18n.t('modelDetail.modal.test.promptLabel')}</span><pre class="model-test-request-prompt-value" id="${modalUiId(modalId, 'request-prompt')}"></pre></div>` +
                `<div class="model-test-request-response u-hidden" id="${modalUiId(modalId, 'request-response')}"><span class="stat-label">${i18n.t('modelDetail.modal.test.responseLabel')}</span><pre class="model-test-request-response-value" id="${modalUiId(modalId, 'request-response-value')}"></pre></div></div>` +
                `<div class="model-test-logs-card u-hidden" id="${modalUiId(modalId, 'logs-card')}"><div class="card-title-bar card-title-bar--clickable model-test-logs-header model-test-logs-header--clickable" id="${modalUiId(modalId, 'logs-header')}" role="button" tabindex="0" aria-expanded="false" aria-controls="${modalUiId(modalId, 'logs-section')}">` +
                `<h4 class="model-test-logs-title">${i18n.t('modelDetail.modal.test.logsTitle')}</h4><button class="ui-icon-button ui-icon-button--titlebar ui-variant-neutral model-test-logs-toggle" id="${modalUiId(modalId, 'logs-toggle')}" data-action="${ACTION_TEST_TOGGLE_LOGS}" ${renderLabelAttributes(toggleLogsAria)} type="button"></button></div>` +
                `<div class="model-test-logs-section" id="${modalUiId(modalId, 'logs-section')}" data-card-content><div class="logs-content model-test-logs" id="${modalUiId(modalId, 'logs')}"></div></div></div>`
        )
    );
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.close') }),
        right: uiHtml`${renderModalFooterActionButton({
            text: i18n.t('modelDetail.modal.test.copyLogs'),
            id: modalUiId(modalId, 'copy-logs'),
            variant: 'primary',
            action: ACTION_TEST_COPY_LOGS,
            className: 'u-hidden'
        })}${renderModalFooterActionButton({
            text: shortLabel,
            ariaLabel: shortAria,
            id: modalUiId(modalId, 'short'),
            variant: 'primary',
            action: ACTION_TEST_SHORT
        })}${renderModalFooterActionButton({
            text: longLabel,
            ariaLabel: longAria,
            id: modalUiId(modalId, 'long'),
            variant: 'warning',
            action: ACTION_TEST_LONG
        })}`
    });
    return renderModalScaffoldMarkup({ id: modalId, className: modalId, header, body, footer, rootAttributes: { 'data-page-scope': 'modelDetail' } });
};

export { renderTestModal };
