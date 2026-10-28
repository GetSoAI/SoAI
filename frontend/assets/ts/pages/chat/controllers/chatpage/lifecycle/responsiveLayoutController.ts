/* SoAI - Chat page responsive layout controller [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/responsiveLayoutController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { CHAT_SELECTORS } from '@features/chat/public.ts';
import { applyWidescreenMode, type ChatUiBehaviorsOwner } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';

type ChatResponsiveLayoutDependencies = ChatConversationStateHost & ChatConversationViewHost & ChatModelSessionHost & PageDomOwnerHost & ChatUiBehaviorsOwner;

class ChatResponsiveLayoutSession {
    readonly #owners: ChatResponsiveLayoutDependencies;

    constructor(owners: ChatResponsiveLayoutDependencies) {
        this.#owners = owners;
    }

    sync(): void {
        void Promise.resolve(this.#owners.uiBehaviors.layout.applySidebarState()).catch((error) => {
            errorHandler.warn('ChatResponsiveLayoutSession', 'Failed to apply the chat sidebar state', ensureError(error));
        });
        applyWidescreenMode(this.#owners.uiBehaviors);
        const messages = this.#owners.pageDom.optional(CHAT_SELECTORS.MESSAGES_CONTAINER);
        if (!(messages instanceof HTMLElement)) return;
        const conversationId = this.#owners.conversationState.currentConversationId;
        const activeComparisonRun = conversationId ? this.#owners.conversationView.activeComparisonRun(conversationId) : null;
        this.#owners.modelSession.syncComparisonPresentation(messages, {
            isCurrentStreaming: Boolean(conversationId && this.#owners.conversationView.isStreaming(conversationId)),
            activeComparisonRun
        });
    }
}

export { ChatResponsiveLayoutSession };
export type { ChatResponsiveLayoutDependencies };
