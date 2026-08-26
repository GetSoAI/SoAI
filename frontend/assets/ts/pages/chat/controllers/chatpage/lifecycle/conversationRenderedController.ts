/* SoAI - Chat page conversation rendered controller [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/conversationRenderedController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/public.ts';
import { reconcileActivityDurationLifecycle } from '@pages/chat/controllers/chatpage/lifecycle/activityDurationLifecycleRuntime.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatConversationRenderOutcome, ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ChatPageConversationRenderedHost extends ChatComposerSurfaceRuntimeOwner, ChatTurnRuntimeOwner, ChatConversationStateHost, ChatRuntimeServicesHost, ChatConversationViewHost, ChatModelSessionHost, PageDomOwnerHost {}

interface ChatConversationRenderedControllerDependencies {
    host: ChatPageConversationRenderedHost;
    handleTokenCounterConversationRendered(conversationId: string | null): void;
    outcome: ChatConversationRenderOutcome;
}

const handleChatConversationRendered = ({ host, handleTokenCounterConversationRendered, outcome }: ChatConversationRenderedControllerDependencies): void => {
    host.turnRuntime.requireAgent().handleConversationRendered();
    host.turnRuntime.requireConversationInputs().handleConversationRendered(host.conversationState.currentConversationId);
    host.composerSurface.requireUi().updateInputQueuePreview();
    handleTokenCounterConversationRendered(host.conversationState.currentConversationId);
    host.modelSession.updateUi();
    if (outcome !== 'messages-unchanged') {
        reconcileActivityDurationLifecycle(host);
    }
    const messages = host.pageDom.optional(CHAT_SELECTORS.MESSAGES_CONTAINER);
    if (!(messages instanceof HTMLElement)) return;
    const conversationId = host.conversationState.currentConversationId;
    const activeComparisonRun = conversationId ? host.conversationView.activeComparisonRun(conversationId) : null;
    host.modelSession.syncComparisonPresentation(messages, {
        isCurrentStreaming: Boolean(conversationId && host.conversationView.isStreaming(conversationId)),
        activeComparisonRun
    });
    if (conversationId !== null && host.runtimeServices.presence.isActivelyViewingConversation(conversationId)) {
        host.composerSurface.requireUi().requestOlderMessagesIfAtTop();
    }
};

export { handleChatConversationRendered };
