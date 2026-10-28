/* SoAI - Chat page actions [frontend/assets/ts/pages/chat/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isChatActionId, isMcpConversationActionId, isSkillAction } from '@features/chat/public.ts';
import { CONTEXT_WINDOW_PRESET_ACTION, isContextWindowPresetAction } from '@core/chat/parameters/contextWindowPresets.ts';

export type ChatActionId = import('@features/chat/public.ts').ChatActionId;
type ChatHostedActionId = import('@features/chat/public.ts').ChatActionId | import('@features/chat/public.ts').McpConversationActionId | import('@features/chat/public.ts').SkillAction | typeof CONTEXT_WINDOW_PRESET_ACTION;

const isChatHostedActionId = (value: string | undefined): value is ChatHostedActionId => isChatActionId(value) || isMcpConversationActionId(value) || isSkillAction(value) || isContextWindowPresetAction(value);

export { isChatActionId, isChatHostedActionId };
export type { ChatHostedActionId };
