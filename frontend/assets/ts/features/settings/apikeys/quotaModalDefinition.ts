/* SoAI - Settings feature quota modal definition [frontend/assets/ts/features/settings/apikeys/quotaModalDefinition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createStandardModalElement } from '@core/modals/scaffoldDom.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { API_KEYS_QUOTA_MODAL_ID } from '@features/settings/apikeys/constants.ts';

const API_KEY_QUOTA_MODAL_BODY_CONTAINER_ID = modalUiId(API_KEYS_QUOTA_MODAL_ID, 'body');
const API_KEY_QUOTA_MODAL_FOOTER_CONTAINER_ID = modalUiId(API_KEYS_QUOTA_MODAL_ID, 'footer');

const settingsApiKeyQuotaModalDefinition: ModalDefinition = {
    id: API_KEYS_QUOTA_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: modalUiSelector(API_KEYS_QUOTA_MODAL_ID, 'mode'),
    createElement: (_options: ModalOpenOptions): HTMLElement =>
        createStandardModalElement(API_KEYS_QUOTA_MODAL_ID, {
            title: i18n.t('settings.apiKeys.quota.modal.title'),
            description: i18n.t('common.modalDescriptions.settingsApiKeyQuota'),
            body: toTrustedUiHtml(`<div id="${API_KEY_QUOTA_MODAL_BODY_CONTAINER_ID}"></div>`),
            footer: EMPTY_UI_HTML,
            contentClassName: 'api-key-quota-modal-content',
            footerLayout: 'split',
            footerId: API_KEY_QUOTA_MODAL_FOOTER_CONTAINER_ID,
            rootAttributes: { 'data-page-scope': 'settings' }
        })
};

export { API_KEY_QUOTA_MODAL_BODY_CONTAINER_ID, API_KEY_QUOTA_MODAL_FOOTER_CONTAINER_ID, settingsApiKeyQuotaModalDefinition };
