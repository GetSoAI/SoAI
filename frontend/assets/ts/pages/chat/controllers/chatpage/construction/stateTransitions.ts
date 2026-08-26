/* SoAI - Chat page state transitions [frontend/assets/ts/pages/chat/controllers/chatpage/construction/stateTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/public.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';

const hasTokenCounterButton = (page: PageDomOwnerHost): boolean => {
    return page.pageDom.query(CHAT_SELECTORS.TOKEN_COUNTER_BTN).length > 0;
};

interface ChatPageConversationTransitionHost extends ChatConversationStateHost, ChatRuntimeServicesHost, PageDomOwnerHost, ChatComposerHost, ChatVoiceSessionHost {}

interface ChatPageModelTransitionHost extends ChatConversationStateHost, PageDomOwnerHost, ChatComposerHost {}

const setCurrentConversationIdForChatPage = (page: ChatPageConversationTransitionHost, conversationId: string | null): void => {
    page.conversationState.currentConversationId = conversationId;
    page.runtimeServices.presence.setConversationId(conversationId);
    if (hasTokenCounterButton(page)) {
        page.composer.handleConversationChanged(conversationId);
    }
    page.voiceSession.handleConversationChanged(conversationId);
};

const setCurrentModelForChatPage = (page: ChatPageModelTransitionHost, modelId: string | null): void => {
    page.conversationState.currentModel = modelId;
    if (hasTokenCounterButton(page)) {
        page.composer.handleModelChanged(modelId);
    }
};

export { setCurrentConversationIdForChatPage, setCurrentModelForChatPage };
