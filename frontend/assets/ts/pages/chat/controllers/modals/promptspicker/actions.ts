/* SoAI - Chat prompts picker modal actions [frontend/assets/ts/pages/chat/controllers/modals/promptspicker/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const CHAT_PROMPTS_PICKER_ACTION_INSERT = 'chat-prompts-picker:insert';
const CHAT_PROMPTS_PICKER_ACTION_EDIT = 'chat-prompts-picker:edit';

export type ChatPromptsPickerActionId = typeof CHAT_PROMPTS_PICKER_ACTION_INSERT | typeof CHAT_PROMPTS_PICKER_ACTION_EDIT;

const actionIds = createActionIdSet<ChatPromptsPickerActionId>(CHAT_PROMPTS_PICKER_ACTION_INSERT, CHAT_PROMPTS_PICKER_ACTION_EDIT);

export const isChatPromptsPickerActionId = actionIds.guard;

export { CHAT_PROMPTS_PICKER_ACTION_EDIT, CHAT_PROMPTS_PICKER_ACTION_INSERT };
