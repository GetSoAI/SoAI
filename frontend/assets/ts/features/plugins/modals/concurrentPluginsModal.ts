/* SoAI - Concurrent plugins modal definition [frontend/assets/ts/features/plugins/modals/concurrentPluginsModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';

import { uiHtml } from '@core/security/uiHtml.ts';
import { PLUGINS_ACTION_CONCURRENT_SAVE, PLUGINS_ACTION_CONCURRENT_SLIDER_INPUT, PLUGINS_ACTION_CONCURRENT_VALUE_INPUT } from '@features/plugins/contracts/pluginActionIds.ts';
import { CONCURRENT_PLUGINS_SLIDER } from '@features/plugins/contracts/pluginPageSupport.ts';

const CONCURRENT_PLUGINS_MODAL_ID = 'concurrent-plugins-modal';

const createConcurrentPluginsModalElement = (): HTMLElement => {
    const { MIN, DEFAULT_MAX, MAX_LIMIT } = CONCURRENT_PLUGINS_SLIDER;
    const modalId = CONCURRENT_PLUGINS_MODAL_ID;
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('plugins.modal.concurrentPlugins.title'),
        description: i18n.t('common.modalDescriptions.pluginsConcurrent'),
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(
        uiHtml`
        <div class="form-group concurrent-plugins-form-group setting-change-surface">
            <label id="${modalUiId(modalId, 'input-label')}" for="${modalUiId(modalId, 'input')}">${i18n.t('plugins.modal.concurrentPlugins.inputLabel')}</label>
            <input
                type="range"
                data-action="${PLUGINS_ACTION_CONCURRENT_SLIDER_INPUT}"
                id="${modalUiId(modalId, 'slider')}"
                class="ui-range concurrent-plugins-slider"
                min="${MIN}"
                max="${DEFAULT_MAX}"
                step="1"
                aria-labelledby="${modalUiId(modalId, 'input-label')}"
            />
            <input
                type="number"
                data-action="${PLUGINS_ACTION_CONCURRENT_VALUE_INPUT}"
                id="${modalUiId(modalId, 'input')}"
                class="form-input concurrent-plugins-input"
                min="${MIN}"
                max="${MAX_LIMIT}"
                step="1"
            />
            <div class="form-error u-hidden" id="${modalUiId(modalId, 'error')}">${i18n.t('plugins.modal.concurrentPlugins.validationError')}</div>
        </div>
    `
    );
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: i18n.t('plugins.modal.concurrentPlugins.close') }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'save'), text: i18n.t('plugins.modal.concurrentPlugins.save'), action: PLUGINS_ACTION_CONCURRENT_SAVE, variant: 'accent' })
    });
    return createModalElement({
        id: modalId,
        rootAttributes: { 'data-page-scope': 'plugins' },
        header,
        body,
        footer
    });
};

const concurrentPluginsModalDefinition: ModalDefinition = Object.freeze({
    id: CONCURRENT_PLUGINS_MODAL_ID,
    layout: 'md',
    initialFocusSelector: modalUiSelector(CONCURRENT_PLUGINS_MODAL_ID, 'slider'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createConcurrentPluginsModalElement()
});

export { CONCURRENT_PLUGINS_MODAL_ID, concurrentPluginsModalDefinition };
