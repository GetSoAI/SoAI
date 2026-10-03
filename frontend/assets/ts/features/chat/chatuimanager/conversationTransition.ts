/* SoAI - Chat conversation visual transition ownership [frontend/assets/ts/features/chat/chatuimanager/conversationTransition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const CHAT_MAIN_CONTAINER_SELECTOR = '.chat-main-container';
const CONVERSATION_TRANSITION_CLASS = 'chat-main-container--conversation-transition';

const resolveMainContainer = (context: ChatUIManagerContext): HTMLElement | null => {
    const candidate = context.dependencies.optionalUI(CHAT_MAIN_CONTAINER_SELECTOR);
    return candidate instanceof HTMLElement ? candidate : null;
};

export const isConversationTransitionActive = (context: ChatUIManagerContext): boolean => {
    return context.state.activeConversationTransitionId !== null;
};

export const beginConversationTransition = (context: ChatUIManagerContext, transitionId: number): void => {
    context.state.activeConversationTransitionId = transitionId;
    context.state.advancedScrollPreviewVisibilityController?.suspend();
    const mainContainer = resolveMainContainer(context);
    if (!mainContainer) {
        return;
    }
    const actions = dom.resolve('.chat-header-actions', mainContainer);
    if (actions instanceof HTMLElement) actions.inert = true;
    context.dependencies.toggleClassName(mainContainer, CONVERSATION_TRANSITION_CLASS, true);
    context.dependencies.updateAttribute(mainContainer, 'aria-busy', 'true');
};

export const completeConversationTransition = (context: ChatUIManagerContext, transitionId: number): void => {
    if (context.state.activeConversationTransitionId !== transitionId) {
        return;
    }
    context.state.activeConversationTransitionId = null;
    const mainContainer = resolveMainContainer(context);
    if (mainContainer) {
        const actions = dom.resolve('.chat-header-actions', mainContainer);
        if (actions instanceof HTMLElement) actions.inert = false;
        context.dependencies.toggleClassName(mainContainer, CONVERSATION_TRANSITION_CLASS, false);
        context.dependencies.updateAttribute(mainContainer, 'aria-busy', null);
    }
    context.state.advancedScrollPreviewVisibilityController?.resume();
};
