/* SoAI - Chat page renderer contracts [frontend/assets/ts/pages/chat/controllers/page/renderer/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewStateHost, ConversationRenderCache } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { ChatPageEmptyState } from '@features/chat/public.ts';

type ChatPageRenderScope = 'conversation-list' | 'conversation-current';

interface ChatConversationListRenderDependencies extends ChatConversationRuntimeOwner, ChatConversationStateHost, ChatSettingsStateHost, ChatViewStateHost, ChatUiTaskScopeHost, ChatConversationViewHost, ChatPagePresentationHost, PageDomOwnerHost {
    conversationToolbarSession: {
        isConversationSelected(conversationId: string): boolean;
    };
    pageContext: { sanitizer: SanitizerApi };
}

interface ChatCurrentConversationStatePort extends ChatComposerSurfaceRuntimeOwner, ChatConversationRuntimeOwner, ChatTurnRuntimeOwner, ChatConversationStateHost, ChatViewStateHost, ChatConversationViewHost, ChatModelSessionHost {}

interface ChatCurrentConversationUiPort extends ChatUiTaskScopeHost, ChatPagePresentationHost, PageDomOwnerHost, PageLifecycleOwnerHost {}

interface ChatCurrentConversationRenderDependencies extends ChatCurrentConversationStatePort, ChatCurrentConversationUiPort, ChatSettingsStateHost {
    pageContext: { sanitizer: SanitizerApi };
    emptyState: ChatPageEmptyState;
}

interface ChatSearchDependencies extends ChatViewStateHost, PageServicesOwnerHost, PageDomOwnerHost {
    renderConversationList(): Promise<void>;
}

export type { ChatConversationListRenderDependencies, ChatCurrentConversationRenderDependencies, ChatPageRenderScope, ChatSearchDependencies, ConversationRenderCache };
