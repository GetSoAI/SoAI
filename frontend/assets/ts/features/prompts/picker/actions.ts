/* SoAI - Prompts picker modal actions [frontend/assets/ts/features/prompts/picker/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const PROMPTS_PICKER_ACTION_INSERT = 'prompts-picker:insert';
const PROMPTS_PICKER_ACTION_EDIT = 'prompts-picker:edit';

export type PromptsPickerActionId = typeof PROMPTS_PICKER_ACTION_INSERT | typeof PROMPTS_PICKER_ACTION_EDIT;

const actionIds = createActionIdSet<PromptsPickerActionId>(PROMPTS_PICKER_ACTION_INSERT, PROMPTS_PICKER_ACTION_EDIT);

export const isPromptsPickerActionId = actionIds.guard;

export { PROMPTS_PICKER_ACTION_EDIT, PROMPTS_PICKER_ACTION_INSERT };
