/* SoAI - Plugins feature concurrent manager constants [frontend/assets/ts/features/plugins/modals/concurrentmanager/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { CONCURRENT_PLUGINS_MODAL_ID } from '@features/plugins/modals/concurrentPluginsModal.ts';

const CONCURRENT_MODAL_ID = CONCURRENT_PLUGINS_MODAL_ID;
const CONCURRENT_FIELD_SELECTOR = '.concurrent-plugins-form-group';
const CONCURRENT_INPUT_SELECTOR = modalUiSelector(CONCURRENT_MODAL_ID, 'input');
const CONCURRENT_SLIDER_SELECTOR = modalUiSelector(CONCURRENT_MODAL_ID, 'slider');
const CONCURRENT_ERROR_SELECTOR = modalUiSelector(CONCURRENT_MODAL_ID, 'error');
const CONCURRENT_ERROR_ID = modalUiId(CONCURRENT_MODAL_ID, 'error');
const CONCURRENT_SAVE_SELECTOR = modalUiSelector(CONCURRENT_MODAL_ID, 'save');
const CONCURRENT_HEADER_CONTEXT_ID = 'concurrent-plugins';

export { CONCURRENT_ERROR_ID, CONCURRENT_ERROR_SELECTOR, CONCURRENT_FIELD_SELECTOR, CONCURRENT_HEADER_CONTEXT_ID, CONCURRENT_INPUT_SELECTOR, CONCURRENT_MODAL_ID, CONCURRENT_SAVE_SELECTOR, CONCURRENT_SLIDER_SELECTOR };
