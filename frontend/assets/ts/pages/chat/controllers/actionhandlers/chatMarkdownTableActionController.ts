/* SoAI - Chat markdown table action controller [frontend/assets/ts/pages/chat/controllers/actionhandlers/chatMarkdownTableActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyMarkdownTableSort, CHAT_ACTIONS } from '@features/chat/public.ts';
import type { ChatActionHandler } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

type ChatMarkdownTableActionId = typeof CHAT_ACTIONS.SORT_MARKDOWN_TABLE;

const createChatMarkdownTableActionHandlers = (): Record<ChatMarkdownTableActionId, ChatActionHandler> => {
    return {
        [CHAT_ACTIONS.SORT_MARKDOWN_TABLE]: (actionElement: HTMLElement): void => applyMarkdownTableSort(actionElement)
    };
};

export { createChatMarkdownTableActionHandlers };
