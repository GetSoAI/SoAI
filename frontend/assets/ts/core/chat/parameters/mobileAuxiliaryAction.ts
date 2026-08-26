/* SoAI - Shared chat mobile auxiliary action [frontend/assets/ts/core/chat/parameters/mobileAuxiliaryAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type ChatMobileAuxiliaryAction = 'none' | 'agent_mode' | 'agent_compact' | 'export' | 'configuration' | 'favorite' | 'tools' | 'token_counter' | 'voice' | 'voice_call' | 'camera' | 'attach' | 'prompts' | 'character_map';

const CHAT_MOBILE_AUXILIARY_ACTION_NONE: ChatMobileAuxiliaryAction = 'none';

const CHAT_MOBILE_AUXILIARY_ACTIONS: ReadonlyArray<ChatMobileAuxiliaryAction> = Object.freeze(['none', 'agent_mode', 'agent_compact', 'export', 'configuration', 'favorite', 'tools', 'token_counter', 'voice', 'voice_call', 'camera', 'attach', 'prompts', 'character_map']);

const CHAT_MOBILE_AUXILIARY_ACTION_SET: ReadonlySet<string> = new Set<ChatMobileAuxiliaryAction>(CHAT_MOBILE_AUXILIARY_ACTIONS);

const isChatMobileAuxiliaryAction = (value: string): value is ChatMobileAuxiliaryAction => {
    return CHAT_MOBILE_AUXILIARY_ACTION_SET.has(value);
};

const normalizeChatMobileAuxiliaryAction = (value: JsonValue | undefined): ChatMobileAuxiliaryAction => {
    if (!isString(value)) {
        return CHAT_MOBILE_AUXILIARY_ACTION_NONE;
    }
    const normalized = value.trim().toLowerCase();
    return isChatMobileAuxiliaryAction(normalized) ? normalized : CHAT_MOBILE_AUXILIARY_ACTION_NONE;
};

export { CHAT_MOBILE_AUXILIARY_ACTION_NONE, CHAT_MOBILE_AUXILIARY_ACTIONS, isChatMobileAuxiliaryAction, normalizeChatMobileAuxiliaryAction };
export type { ChatMobileAuxiliaryAction };
