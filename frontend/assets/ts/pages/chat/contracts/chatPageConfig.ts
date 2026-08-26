/* SoAI - Chat page configuration contract [frontend/assets/ts/pages/chat/contracts/chatPageConfig.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconDefinition } from '@core/routing/pages/pagetypes/public.ts';
import { CHAT_TEXT_ZOOM_DEFAULT, CHAT_TEXT_ZOOM_MAX, CHAT_TEXT_ZOOM_MIN, CHAT_TEXT_ZOOM_STEP } from '@core/chat/parameters/textZoom.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { CHAT_ICON_SIZE_MD, CHAT_ICON_SIZE_SM, CHAT_SELECTORS } from '@features/chat/public.ts';

const DEFAULT_TEXT_ZOOM = CHAT_TEXT_ZOOM_DEFAULT;

const icon = (name: IconName, options: IconOptions): IconDefinition => ({ name, options });

const CHAT_BASE_ICON_MAP: Record<string, IconDefinition> = {
    '.new-conversation-btn': icon('add', CHAT_ICON_SIZE_SM),
    '.new-conversation-header-btn': icon('add', CHAT_ICON_SIZE_SM),
    '.configuration-toggle-btn:not(.configuration-toggle-btn--dropdown)': icon('model-config', CHAT_ICON_SIZE_SM),
    '.configuration-toggle-btn--dropdown .chat-action-icon': icon('model-config', CHAT_ICON_SIZE_SM),
    '.agent-compact-btn .chat-action-icon': icon('agent-compact', CHAT_ICON_SIZE_SM),
    '.export-btn .chat-action-icon': icon('download', CHAT_ICON_SIZE_SM),
    '.header-favorite-btn .chat-action-icon': icon('star', CHAT_ICON_SIZE_SM),
    '.favorite-toggle-btn .chat-action-icon': icon('star', CHAT_ICON_SIZE_SM),
    '.tools-toggle-btn .chat-action-icon': icon('tools-toggle', CHAT_ICON_SIZE_SM),
    '.chat-overflow-trigger .chat-action-icon': icon('ellipsis', CHAT_ICON_SIZE_SM),
    '.chat-toolbar-total-conversations-icon': icon('chat', { size: 12, strokeWidth: 1.5 })
};
Object.freeze(CHAT_BASE_ICON_MAP);

const CHAT_INPUT_ACTION_ICON_MAP: Record<string, IconDefinition> = {
    '.chat-token-counter-menu .chat-action-icon': icon('info', CHAT_ICON_SIZE_MD),
    '.microphone-btn .chat-action-icon--microphone': icon('microphone', CHAT_ICON_SIZE_MD),
    '.microphone-btn .chat-action-icon--stop': icon('stop', CHAT_ICON_SIZE_MD),
    '.call-btn .chat-action-icon': icon('call', CHAT_ICON_SIZE_MD),
    '.attach-add-btn .chat-action-icon': icon('paperclip', CHAT_ICON_SIZE_MD),
    '.camera-btn .chat-action-icon': icon('camera', CHAT_ICON_SIZE_MD),
    '.goto-prompts-btn .chat-action-icon': icon('prompt', CHAT_ICON_SIZE_MD),
    [`${CHAT_SELECTORS.CHARACTER_MAP_BTN} .chat-action-icon`]: icon('file-font', CHAT_ICON_SIZE_MD),
    '.chat-action-btn': icon('send', CHAT_ICON_SIZE_MD)
};
Object.freeze(CHAT_INPUT_ACTION_ICON_MAP);

const ICON_MAP = Object.freeze({ ...CHAT_BASE_ICON_MAP, ...CHAT_INPUT_ACTION_ICON_MAP });

export { CHAT_TEXT_ZOOM_MAX, CHAT_TEXT_ZOOM_MIN, CHAT_TEXT_ZOOM_STEP, DEFAULT_TEXT_ZOOM, CHAT_BASE_ICON_MAP, CHAT_INPUT_ACTION_ICON_MAP, ICON_MAP };
