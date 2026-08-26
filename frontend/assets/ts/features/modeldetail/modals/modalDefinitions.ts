/* SoAI - Model Detail modal definitions registered by app bootstrap [frontend/assets/ts/features/modeldetail/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElementFromMarkup } from '@core/modals/scaffoldDom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { MODEL_DETAIL_TEST_MODAL_ID } from '@features/modeldetail/modals/constants.ts';
import { renderTestModal } from '@features/modeldetail/modals/markup.ts';

const modelDetailTestModalDefinition: ModalDefinition = Object.freeze({
    id: MODEL_DETAIL_TEST_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: modalUiSelector(MODEL_DETAIL_TEST_MODAL_ID, 'short'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createModalElementFromMarkup(MODEL_DETAIL_TEST_MODAL_ID, renderTestModal())
});

const MODEL_DETAIL_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([modelDetailTestModalDefinition]);

export { MODEL_DETAIL_MODAL_DEFINITIONS };
