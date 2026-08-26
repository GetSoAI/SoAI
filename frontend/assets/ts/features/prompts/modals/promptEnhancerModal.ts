/* SoAI - Prompt enhancer modal definition [frontend/assets/ts/features/prompts/modals/promptEnhancerModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';

import { uiHtml } from '@core/security/uiHtml.ts';
import { renderDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { PROMPTS_ENHANCER_MODAL_ID } from '@features/prompts/modals/constants.ts';

const createPromptEnhancerModalElement = (): HTMLElement => {
    const modalId = PROMPTS_ENHANCER_MODAL_ID;
    const titleId = modalUiId(modalId, 'title');
    const modelSettingId = modalUiId(modalId, 'model-setting');
    const modelSelectId = modalUiId(modalId, 'model-select');
    const modelHelpId = modalUiId(modalId, 'model-help');
    const statusBadgeId = modalUiId(modalId, 'status-badge');
    const statusLedId = modalUiId(modalId, 'status-led');
    const statusValueId = modalUiId(modalId, 'status-value');
    const errorId = modalUiId(modalId, 'error');
    const panesId = modalUiId(modalId, 'panes');
    const originalPaneId = modalUiId(modalId, 'original-pane');
    const originalCharCountId = modalUiId(modalId, 'original-char-count');
    const originalId = modalUiId(modalId, 'original');
    const enhancedPaneId = modalUiId(modalId, 'enhanced-pane');
    const enhancedDoneLedId = modalUiId(modalId, 'enhanced-done-led');
    const enhancedCharCountId = modalUiId(modalId, 'enhanced-char-count');
    const outputSpinnerId = modalUiId(modalId, 'output-spinner');
    const waitMessageId = modalUiId(modalId, 'wait-message');
    const outputId = modalUiId(modalId, 'output');
    const closeButtonId = modalUiId(modalId, 'close');
    const runButtonId = modalUiId(modalId, 'run');
    const copyButtonId = modalUiId(modalId, 'copy');
    const saveNewButtonId = modalUiId(modalId, 'save-new');
    const modelSelectMarkup = renderDropdownSelectControl({
        selectMarkup: `<select class="model-selector form-input" id="${modelSelectId}"></select>`
    });
    const separatorIcon = getIconSync('chevron-right', {
        size: 20,
        strokeWidth: 2,
        className: 'prompt-enhancer-pane-separator-icon'
    });
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('prompts.enhancer.title'),
        description: i18n.t('common.modalDescriptions.promptEnhancer'),
        titleId,
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(uiHtml`
        <div class="prompt-modal-content prompt-enhancer-layout">
            <div class="prompt-enhancer-meta">
                <div class="prompt-enhancer-meta-row" id="${modelSettingId}">
                    <span class="prompt-enhancer-meta-label">${i18n.t('prompts.enhancer.model')}</span>
                    <div class="setting-control">
                        ${toTrustedUiHtml(modelSelectMarkup)}
                    </div>
                </div>
                <div class="prompt-enhancer-meta-row prompt-enhancer-meta-row--hint">
                    <span class="prompt-enhancer-meta-value prompt-enhancer-meta-hint" id="${modelHelpId}"></span>
                </div>
                <div class="prompt-enhancer-meta-row">
                    <span class="prompt-enhancer-meta-label">${i18n.t('prompts.enhancer.status.label')}</span>
                    <span class="ui-status-badge neutral" id="${statusBadgeId}">
                        <span class="status-indicator grey" id="${statusLedId}"></span>
                        <span id="${statusValueId}"></span>
                    </span>
                </div>
                <div class="prompt-enhancer-error u-hidden" id="${errorId}"></div>
            </div>
            <div class="prompt-enhancer-panes" id="${panesId}">
                <section class="prompt-enhancer-pane prompt-enhancer-pane--original u-hidden" id="${originalPaneId}" aria-hidden="true">
                    <div class="card-title-bar card-title-bar--no-border">
                        <h4 class="card-title">${i18n.t('prompts.enhancer.panes.original')}</h4>
                        <span class="prompt-enhancer-char-count u-hidden" id="${originalCharCountId}"></span>
                    </div>
                    <div class="prompt-enhancer-pane-body">
                        <pre class="prompt-enhancer-text" id="${originalId}"></pre>
                    </div>
                </section>
                <span class="prompt-enhancer-pane-separator" aria-hidden="true">${separatorIcon}</span>
                <section class="prompt-enhancer-pane prompt-enhancer-pane--enhanced" id="${enhancedPaneId}">
                    <div class="card-title-bar card-title-bar--no-border">
                        <div class="prompt-enhancer-title-group">
                            <h4 class="card-title">${i18n.t('prompts.enhancer.panes.enhanced')}</h4>
                            <span class="prompt-enhancer-done-led u-hidden" id="${enhancedDoneLedId}" aria-hidden="true"></span>
                        </div>
                        <span class="prompt-enhancer-char-count u-hidden" id="${enhancedCharCountId}"></span>
                    </div>
                    <div class="prompt-enhancer-pane-body">
                        <div class="prompt-enhancer-loading-center">
                            <div class="prompt-enhancer-output-spinner u-hidden" id="${outputSpinnerId}" aria-hidden="true">
                                <span class="spinner"></span>
                            </div>
                            <div class="prompt-enhancer-output-wait-message u-hidden" id="${waitMessageId}">
                                ${i18n.t('prompts.enhancer.pleaseWait')}
                            </div>
                        </div>
                        <pre class="prompt-enhancer-text prompt-enhancer-output prompt-enhancer-output--plain" id="${outputId}"></pre>
                    </div>
                </section>
            </div>
        </div>
    `);
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, id: closeButtonId, text: i18n.t('common.close') }),
        right: uiHtml`${renderModalFooterActionButton({ id: runButtonId, text: i18n.t('prompts.enhancer.actions.run'), variant: 'violet' })}${renderModalFooterActionButton({ id: copyButtonId, text: i18n.t('prompts.enhancer.actions.copy'), variant: 'primary' })}${renderModalFooterActionButton({ id: saveNewButtonId, text: i18n.t('prompts.enhancer.actions.saveAsNew'), variant: 'accent' })}`
    });
    return createModalElement({
        id: modalId,
        className: 'prompt-view-modal prompt-enhancer-modal',
        labelledBy: titleId,
        rootAttributes: { 'data-page-scope': 'prompts' },
        header,
        body,
        footer
    });
};

const promptEnhancerModalDefinition: ModalDefinition = Object.freeze({
    id: PROMPTS_ENHANCER_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(PROMPTS_ENHANCER_MODAL_ID, 'model-select'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createPromptEnhancerModalElement()
});

export { promptEnhancerModalDefinition };
