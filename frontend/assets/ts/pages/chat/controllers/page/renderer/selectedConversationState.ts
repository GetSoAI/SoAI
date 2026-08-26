/* SoAI - Chat page selected conversation state [frontend/assets/ts/pages/chat/controllers/page/renderer/selectedConversationState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { Conversation } from '@features/chat/public.ts';
import type { ChatCurrentConversationRenderDependencies } from '@pages/chat/controllers/page/renderer/contracts.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';

type SelectedConversationViewState = 'messages' | 'empty' | 'loading' | 'error';

type SelectedConversationViewStateHost = Pick<ChatCurrentConversationRenderDependencies, 'turnRuntime'> & ChatConversationStateHost;

const resolveSelectedConversationViewState = (host: SelectedConversationViewStateHost, conversation: Conversation | null, renderableCount: number, isCurrentStreaming: boolean, conversationKey: string): SelectedConversationViewState => {
    const hydrationState = host.conversationState.selectedConversationHydrationState;
    const isHydratingSelectedConversation = hydrationState.conversationId === conversationKey;
    if (isHydratingSelectedConversation && hydrationState.status === 'error' && !isCurrentStreaming) {
        return 'error';
    }
    if (isHydratingSelectedConversation && hydrationState.status === 'loading') {
        return 'loading';
    }
    if (!conversation) {
        return 'empty';
    }
    if (conversation.messagesHydrated !== true && !isCurrentStreaming) {
        return 'messages';
    }
    if (renderableCount > 0 || isCurrentStreaming) {
        return 'messages';
    }
    if (conversationKey && host.turnRuntime.requireAgent().resolveRunningTurnId(conversationKey) !== null) {
        return 'messages';
    }
    return 'empty';
};

const getSelectedConversationLoadingStateHTML = (host: ChatCurrentConversationRenderDependencies): TrustedHtml => {
    const sanitize = host.pageContext.sanitizer.html;
    return toTrustedUiHtml(`<div class="chat-page-empty-state" data-state="loading">
        <div class="chat-page-loading-row" role="status" aria-live="polite">
            <span class="loading-spinner chat-page-loading-spinner" aria-hidden="true"></span>
            <p class="chat-page-empty-state-subtitle">${sanitize(i18n.t('chat.conversation.loadingMessages'))}</p>
        </div>
    </div>`);
};

const getSelectedConversationErrorStateHTML = (host: ChatCurrentConversationRenderDependencies): TrustedHtml => {
    const sanitize = host.pageContext.sanitizer.html;
    return toTrustedUiHtml(`<div class="chat-page-empty-state" data-state="error">
        <div class="chat-page-empty-state-header">
            <div class="chat-page-empty-state-title-row">
                <h2 class="chat-page-empty-state-heading">${sanitize(i18n.t('common.error'))}</h2>
            </div>
            <p class="chat-page-empty-state-subtitle">${sanitize(i18n.t('chat.errors.conversationLoadFailed'))}</p>
        </div>
    </div>`);
};

export { getSelectedConversationErrorStateHTML, getSelectedConversationLoadingStateHTML, resolveSelectedConversationViewState };
export type { SelectedConversationViewState, SelectedConversationViewStateHost };
