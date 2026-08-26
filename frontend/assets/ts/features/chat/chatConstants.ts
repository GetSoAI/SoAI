/* SoAI - Chat feature constants [frontend/assets/ts/features/chat/chatConstants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

const CHAT_ICON_SIZE_XS: IconOptions = Object.freeze({ size: 14, strokeWidth: 1.5 });
const CHAT_ICON_SIZE_SM: IconOptions = Object.freeze({ size: 16, strokeWidth: 1.5 });
const CHAT_ICON_SIZE_MD: IconOptions = Object.freeze({ size: 18, strokeWidth: 1.5 });
const CHAT_ICON_SIZE_LG: IconOptions = Object.freeze({ size: 24, strokeWidth: 1.5 });

const CHAT_ACTION_ID_OPEN_MODEL_DETAIL = 'chat:open-model-detail';
const CHAT_ACTION_ID_SECRET_PROMPT_SUBMIT = 'chat:secret-prompt-submit';
const CHAT_ACTION_ID_SECRET_PROMPT_CANCEL = 'chat:secret-prompt-cancel';
const CHAT_CHARACTER_MAP_BUTTON_CLASS = 'character-map-btn';

const CHAT_EVENT_MODEL_SELECTION_CHANGED = 'soai:chat:model-selection-changed';

const CONVERSATION_TITLE_MAX_LENGTH = 250;
const CHAT_MOBILE_SIDEBAR_BREAKPOINT_PX = 900;
const CHAT_ACTIVITY_COMPACT_BREAKPOINT_PX = 768;

const CHAT_ACTIVITY_DURATION_REFRESH_INTERVAL_MS = 250;
const CHAT_ATTACHMENT_INLINE_LIMIT = 6;
const CHAT_SCROLL_BOTTOM_THRESHOLD = 4;

const CHAT_SELECTORS = Object.freeze({
    INPUT: '.chat-input',
    ACTION_BTN: '.chat-action-btn',
    ATTACH_BTN: '.attach-add-btn',
    MICROPHONE_BTN: '.microphone-btn',
    CALL_BTN: '.call-btn',
    TOKEN_COUNTER_BTN: '.chat-token-counter-btn',
    CHARACTER_MAP_BTN: `.${CHAT_CHARACTER_MAP_BUTTON_CLASS}`,
    CAMERA_BTN: '.camera-btn',
    PREVIEW: '.attached-files-preview',
    INPUT_QUEUE_PREVIEW: '.input-queue-preview',
    TOOL_APPROVAL_PREVIEW: '.tool-approval-preview',
    ASK_USER_PREVIEW: '.ask-user-preview',
    SECRET_PROMPT_PREVIEW: '.secret-prompt-preview',
    VOICE_RECORDING_PREVIEW: '.voice-recording-preview',
    MESSAGES_AREA: '.chat-messages-area',
    MESSAGES: '.chat-messages',
    MESSAGES_CONTAINER: '#chat-messages',
    CONVERSATIONS_LIST: '#conversations-list',
    CONVERSATIONS_LIST_EMPTY: '#conversations-list-empty',
    SIDEBAR: '.chat-sidebar',
    SIDEBAR_TOGGLE: '.chat-sidebar-toggle-btn',
    CONFIGURATION_TOGGLE: '.configuration-toggle-btn',
    MCP_DEFAULT_TOOLS_TRIGGER: '.mcp-default-tools-trigger',
    PROMPTS_BTN: '.goto-prompts-btn',
    TOOLS_TOGGLE_BTN: '.tools-toggle-btn',
    EXPORT_BTN: '.export-btn',
    NEW_CONVERSATION: '.new-conversation-btn',
    CONVERSATION_TITLE: '.conversation-title',
    CONVERSATION_TITLE_INPUT: '.conversation-title-input',
    CONVERSATION_LIST_TITLE_INPUT: '.conversation-item-title-input',
    TOOLBAR_CONTAINER: '#chat-toolbar-container',
    SEARCH_CONTAINER: '.chat-search-container'
});

export { CHAT_ACTION_ID_OPEN_MODEL_DETAIL, CHAT_ACTION_ID_SECRET_PROMPT_SUBMIT, CHAT_ACTION_ID_SECRET_PROMPT_CANCEL, CHAT_CHARACTER_MAP_BUTTON_CLASS, CHAT_EVENT_MODEL_SELECTION_CHANGED, CONVERSATION_TITLE_MAX_LENGTH, CHAT_MOBILE_SIDEBAR_BREAKPOINT_PX, CHAT_ACTIVITY_COMPACT_BREAKPOINT_PX, CHAT_ACTIVITY_DURATION_REFRESH_INTERVAL_MS, CHAT_ATTACHMENT_INLINE_LIMIT, CHAT_SCROLL_BOTTOM_THRESHOLD, CHAT_ICON_SIZE_XS, CHAT_ICON_SIZE_SM, CHAT_ICON_SIZE_MD, CHAT_ICON_SIZE_LG, CHAT_SELECTORS };
export type { IconOptions };
