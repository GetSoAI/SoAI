/* SoAI - Chat page render cache invalidation policy [frontend/assets/ts/pages/chat/controllers/page/renderer/chatMarkupInvalidationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';

const invalidateCurrentConversationMarkup = (target: ChatViewStateHost): void => {
    if (target.viewState.conversationRenderCache?.viewState === 'messages') {
        target.viewState.conversationRenderCache.renderSignatureByDomId.clear();
        return;
    }
    target.viewState.conversationRenderCache = null;
};

export { invalidateCurrentConversationMarkup };
