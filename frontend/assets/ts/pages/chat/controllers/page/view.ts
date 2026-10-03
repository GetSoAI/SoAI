/* SoAI - Chat page control layer rendering [frontend/assets/ts/pages/chat/controllers/page/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConversationRenderOutcome } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatConversationListRenderDependencies, ChatCurrentConversationRenderDependencies, ChatPageRenderScope, ChatSearchDependencies } from '@pages/chat/controllers/page/renderer/contracts.ts';
import { renderCurrentConversationView } from '@pages/chat/controllers/page/renderer/currentConversation.ts';
import { initializeChatSearch } from '@pages/chat/controllers/page/renderer/search.ts';

const refreshConversationsUI = async (dependencies: { renderList(): Promise<void>; current: ChatCurrentConversationRenderDependencies; updateHeaderActions(): void }): Promise<ChatConversationRenderOutcome> => {
    const signal = dependencies.current.pageLifecycle.signal();
    if (signal?.aborted) return 'superseded';
    await dependencies.renderList();
    if (signal?.aborted) return 'superseded';
    const outcome = await renderCurrentConversationView(dependencies.current);
    if (signal?.aborted) return 'superseded';
    dependencies.updateHeaderActions();
    return outcome;
};

export { initializeChatSearch, refreshConversationsUI, renderCurrentConversationView };
export type { ChatConversationListRenderDependencies, ChatCurrentConversationRenderDependencies, ChatPageRenderScope, ChatSearchDependencies };
export type { ChatConversationRenderOutcome };
