/* SoAI - Hardware page modal definitions registered by app bootstrap [frontend/assets/ts/features/hardware/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderModalLoadingState, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, HARDWARE_SOAIBENCH_RUN_MODAL_ID, HARDWARE_SYSTEM_INFO_MODAL_ID } from '@features/hardware/modals/constants.ts';
import { HARDWARE_SOAIBENCH_HISTORY_COPY_ACTION, HARDWARE_SOAIBENCH_HISTORY_DOWNLOAD_ACTION } from '@features/hardware/modals/soaibenchhistory/constants.ts';

const createSystemInfoModalElement = (): HTMLElement => {
    const modalId = HARDWARE_SYSTEM_INFO_MODAL_ID;
    const closeAriaLabel = i18n.t('hardware.modals.systemInfo.ariaLabels.close');
    const copyAriaLabel = i18n.t('hardware.modals.systemInfo.ariaLabels.copy');
    const downloadAriaLabel = i18n.t('hardware.modals.systemInfo.ariaLabels.download');
    const closeText = i18n.t('hardware.modals.systemInfo.close');
    const copyText = i18n.t('hardware.modals.systemInfo.copy');
    const downloadText = i18n.t('hardware.modals.systemInfo.download');
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('hardware.modals.systemInfo.title'),
        description: i18n.t('common.modalDescriptions.hardwareSystemInfo'),
        titleId,
        closeLabel: closeAriaLabel
    });
    const body = renderModalBody(
        uiHtml`
            ${renderModalLoadingState({ text: i18n.t('hardware.modals.systemInfo.generating'), hidden: true, overlay: true, className: 'system-info-loading' })}
            <pre class="system-info-content u-stretch" id="${modalUiId(modalId, 'content')}"></pre>
        `
    );
    const footer = renderSplitModalFooter({
        left: uiHtml`${renderModalFooterCloseButton({ modalId, text: closeText, ariaLabel: closeAriaLabel })}<label class="toggle-switch system-info-anonymize-toggle">
                <input type="checkbox" data-action="hardware.systemInfo.anonymize" id="${modalUiId(modalId, 'anonymize-toggle')}" />
                <span class="slider"></span>
                <span class="toggle-label">${i18n.t('hardware.modals.systemInfo.anonymize')}</span>
            </label>`,
        right: uiHtml`${renderModalFooterActionButton({ text: copyText, ariaLabel: copyAriaLabel, id: modalUiId(modalId, 'copy'), variant: 'primary', action: 'hardware.systemInfo.copy' })}${renderModalFooterActionButton({ text: downloadText, ariaLabel: downloadAriaLabel, id: modalUiId(modalId, 'download'), variant: 'accent', action: 'hardware.systemInfo.download' })}`
    });
    return createModalElement({
        id: modalId,
        className: modalId,
        contentClassName: `${modalId}-content`,
        rootAttributes: { 'data-page-scope': 'hardware' },
        header,
        body,
        footer
    });
};

const createSoAIBenchHistoryModalElement = (): HTMLElement => {
    const modalId = HARDWARE_SOAIBENCH_HISTORY_MODAL_ID;
    const closeAriaLabel = i18n.t('hardware.modals.soaibenchHistory.ariaLabels.close');
    const copyAriaLabel = i18n.t('hardware.modals.soaibenchHistory.ariaLabels.copy');
    const downloadAriaLabel = i18n.t('hardware.modals.soaibenchHistory.ariaLabels.download');
    const closeText = i18n.t('hardware.modals.soaibenchHistory.close');
    const copyText = i18n.t('hardware.modals.soaibenchHistory.copy');
    const downloadText = i18n.t('hardware.modals.soaibenchHistory.download');
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('hardware.modals.soaibenchHistory.title'),
        description: i18n.t('hardware.modals.soaibenchHistory.description'),
        titleId,
        closeLabel: closeAriaLabel
    });
    const body = renderModalBody(
        uiHtml`
            ${renderModalLoadingState({ text: i18n.t('hardware.modals.soaibenchHistory.loading'), hidden: true, overlay: true, className: 'hardware-soaibench-history-loading' })}
            <section class="card metrics-panel hardware-soaibench-history-card">
                <div class="section-content" id="${modalUiId(modalId, 'content')}"></div>
            </section>
        `,
        { className: 'modal-body--relative' }
    );
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: closeText, ariaLabel: closeAriaLabel }),
        right: uiHtml`${renderModalFooterActionButton({ text: copyText, ariaLabel: copyAriaLabel, id: modalUiId(modalId, 'copy'), variant: 'primary', action: HARDWARE_SOAIBENCH_HISTORY_COPY_ACTION, disabled: true })}${renderModalFooterActionButton({ text: downloadText, ariaLabel: downloadAriaLabel, id: modalUiId(modalId, 'download'), variant: 'success', action: HARDWARE_SOAIBENCH_HISTORY_DOWNLOAD_ACTION, disabled: true })}`
    });
    return createModalElement({
        id: modalId,
        className: modalId,
        labelledBy: titleId,
        rootAttributes: { 'data-page-scope': 'hardware' },
        header,
        body,
        footer
    });
};

const createSoAIBenchRunModalElement = (): HTMLElement => {
    const modalId = HARDWARE_SOAIBENCH_RUN_MODAL_ID;
    const closeAriaLabel = i18n.t('hardware.modals.soaibenchRun.ariaLabels.close');
    const historyAriaLabel = i18n.t('hardware.modals.soaibenchRun.ariaLabels.history');
    const copyAriaLabel = i18n.t('hardware.modals.soaibenchRun.ariaLabels.copy');
    const downloadAriaLabel = i18n.t('hardware.modals.soaibenchRun.ariaLabels.download');
    const startAriaLabel = i18n.t('hardware.modals.soaibenchRun.ariaLabels.start');
    const closeText = i18n.t('hardware.modals.soaibenchRun.close');
    const historyText = i18n.t('hardware.modals.soaibenchRun.history');
    const copyText = i18n.t('hardware.modals.soaibenchRun.copy');
    const downloadText = i18n.t('hardware.modals.soaibenchRun.download');
    const publishText = i18n.t('hardware.soaibenchPublication.action');
    const startText = i18n.t('hardware.modals.soaibenchRun.start');
    const titleId = modalUiId(modalId, 'title');
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('hardware.modals.soaibenchRun.title'),
        description: i18n.t('hardware.modals.soaibenchRun.description'),
        titleId,
        closeLabel: closeAriaLabel
    });
    const body = renderModalBody(uiHtml`<div id="${modalUiId(modalId, 'body')}" class="hardware-soaibench-run-body"></div>`);
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, id: modalUiId(modalId, 'close'), text: closeText, ariaLabel: closeAriaLabel }),
        right: uiHtml`${renderModalFooterActionButton({ text: historyText, ariaLabel: historyAriaLabel, id: modalUiId(modalId, 'history'), variant: 'neutral', action: 'hardware.gpu.soaibench.history', disabled: true, attributes: { hidden: true } })}${renderModalFooterActionButton({ text: copyText, ariaLabel: copyAriaLabel, id: modalUiId(modalId, 'copy'), variant: 'primary', action: 'hardware.gpu.soaibench.run.copy', disabled: true })}${renderModalFooterActionButton({ text: downloadText, ariaLabel: downloadAriaLabel, id: modalUiId(modalId, 'download'), variant: 'accent', action: 'hardware.gpu.soaibench.run.download', disabled: true })}${renderModalFooterActionButton({ text: publishText, ariaLabel: i18n.t('hardware.soaibenchPublication.ariaLabel'), id: modalUiId(modalId, 'publish'), variant: 'violet', action: 'hardware.gpu.soaibench.run.publish', disabled: true, attributes: { hidden: true } })}${renderModalFooterActionButton({ text: startText, ariaLabel: startAriaLabel, id: modalUiId(modalId, 'start'), variant: 'accent', action: 'hardware.gpu.soaibench.start.confirm' })}`
    });
    return createModalElement({
        id: modalId,
        className: modalId,
        labelledBy: titleId,
        rootAttributes: { 'data-page-scope': 'hardware' },
        header,
        body,
        footer
    });
};

const HARDWARE_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([
    {
        id: HARDWARE_SYSTEM_INFO_MODAL_ID,
        layout: 'lg',
        initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
        createElement: (_options: ModalOpenOptions): HTMLElement => createSystemInfoModalElement()
    },
    {
        id: HARDWARE_SOAIBENCH_HISTORY_MODAL_ID,
        layout: 'xl',
        initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
        createElement: (_options: ModalOpenOptions): HTMLElement => createSoAIBenchHistoryModalElement()
    },
    {
        id: HARDWARE_SOAIBENCH_RUN_MODAL_ID,
        layout: 'lg',
        initialFocusSelector: modalUiSelector(HARDWARE_SOAIBENCH_RUN_MODAL_ID, 'start'),
        createElement: (_options: ModalOpenOptions): HTMLElement => createSoAIBenchRunModalElement()
    }
]);

export { HARDWARE_MODAL_DEFINITIONS };
