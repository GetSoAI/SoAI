/* SoAI - Shared layout chat completion watcher [frontend/assets/ts/core/layout/sidebar/chatCompletionWatcher.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireChatConversationAttention } from '@core/chat/streamServiceAccess.ts';
import type { SidebarLinkIndicatorController } from '@core/layout/sidebar/linkIndicator.ts';

const CHAT_INDICATOR_ERROR_CLASS = 'sidebar-chat-indicator--error';

const subscribeChatCompletionWatcher = (chatIndicator: SidebarLinkIndicatorController): (() => void) => {
    const attention = requireChatConversationAttention();
    const syncIndicator = (): void => {
        const summary = attention.getTerminalIndicatorSummary();
        chatIndicator.setVariantClassName(summary === 'error' ? CHAT_INDICATOR_ERROR_CLASS : null);
        chatIndicator.setVisible(summary !== null);
    };

    const unsubscribeAttention = attention.subscribeTerminalIndicators(syncIndicator);
    syncIndicator();
    return () => {
        unsubscribeAttention();
    };
};

export { subscribeChatCompletionWatcher };
