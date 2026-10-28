/* SoAI - Prompts modal definitions registered by app bootstrap [frontend/assets/ts/features/prompts/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import { promptEnhancerModalDefinition } from '@features/prompts/modals/promptEnhancerModal.ts';

import { promptsPickerModalDefinition } from '@features/prompts/modals/promptsPickerModal.ts';

const PROMPTS_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([promptEnhancerModalDefinition, promptsPickerModalDefinition]);

export { PROMPTS_MODAL_DEFINITIONS };
