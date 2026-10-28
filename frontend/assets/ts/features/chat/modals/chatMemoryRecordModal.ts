/* SoAI - Memory graph record management modal [frontend/assets/ts/features/chat/modals/chatMemoryRecordModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import { createStandardModalElement } from '@core/modals/scaffoldDom.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { CHAT_MEMORY_RECORD_MODAL_ID } from '@features/chat/modals/constants.ts';

const CHAT_MEMORY_RECORD_MODAL_DEFINITION: ModalDefinition = {
    id: CHAT_MEMORY_RECORD_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: () =>
        createStandardModalElement(CHAT_MEMORY_RECORD_MODAL_ID, {
            title: uiHtml`<span data-memory-record-title></span>`,
            body: uiHtml`<div data-memory-record-content class="chat-memory-record"></div>`,
            footer: renderModalFooterCloseButton({ modalId: CHAT_MEMORY_RECORD_MODAL_ID, text: i18n.t('common.close') }),
            closeLabel: i18n.t('common.close'),
            rootAttributes: { 'data-page-scope': 'chat' }
        })
};

export { CHAT_MEMORY_RECORD_MODAL_DEFINITION };
