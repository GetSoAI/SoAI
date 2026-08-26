/* SoAI - Chat page conversation list action handlers [frontend/assets/ts/pages/chat/controllers/actionhandlers/core/conversationListActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isElementNode } from '@core/typeGuards.ts';
import { CHAT_ACTIONS } from '@features/chat/public.ts';
import { createStoppedPropagationActionHandler, requireCurrentConversationId, runConversationControllerAction, runConversationControllerUiTask, withStoppedPropagation } from '@pages/chat/controllers/actionhandlers/core/effects.ts';
import type { ChatActionHandler, ChatConversationActionPort, ChatConversationActionsControllerContract, ChatExecutionActionPort, ChatPresentationActionPort, ChatToolbarActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

interface ChatConversationListActionsHost {
    conversation: ChatConversationActionPort;
    execution: ChatExecutionActionPort;
    presentation: ChatPresentationActionPort;
    toolbar: ChatToolbarActionPort;
}

type ChatConversationListActionId = typeof CHAT_ACTIONS.DELETE_CONVERSATION | typeof CHAT_ACTIONS.EXPORT_CONVERSATION_ITEM | typeof CHAT_ACTIONS.OPEN_CONVERSATION_COLOR_PICKER | typeof CHAT_ACTIONS.TOGGLE_CURRENT_CONVERSATION_FAVORITE | typeof CHAT_ACTIONS.SWITCH_CONVERSATION | typeof CHAT_ACTIONS.CONVERSATION_TITLE_SAVE | typeof CHAT_ACTIONS.CONVERSATION_TITLE_CANCEL | typeof CHAT_ACTIONS.CONVERSATION_LIST_TITLE_SAVE | typeof CHAT_ACTIONS.CONVERSATION_LIST_TITLE_CANCEL | typeof CHAT_ACTIONS.START_CONVERSATION_RENAME | typeof CHAT_ACTIONS.START_CONVERSATION_TITLE_EDIT;

const requireConversationItemId = (host: ChatConversationListActionsHost, actionElement: HTMLElement): string => {
    return host.conversation.requireId(actionElement, '.conversation-item');
};

const createStoppedPropagationConversationItemActionHandler = (host: ChatConversationListActionsHost, action: (actionElement: HTMLElement, conversationId: string) => void): ChatActionHandler => {
    return createStoppedPropagationActionHandler((actionElement: HTMLElement) => {
        const conversationId = requireConversationItemId(host, actionElement);
        action(actionElement, conversationId);
    });
};

const shouldSkipConversationSwitch = (event: Event): boolean => {
    if (!isElementNode(event.target)) {
        return false;
    }
    const target = event.target;
    if (target.closest('.conversation-item-actions')) {
        return true;
    }
    if (target.closest('.chat-conversation-color-picker')) {
        return true;
    }
    return Boolean(target.closest('.conversation-item-title-editor'));
};

const createConversationControllerAction = (host: ChatConversationListActionsHost, action: (controller: ChatConversationActionsControllerContract) => void): (() => void) => {
    return (): void => {
        runConversationControllerAction(host, action);
    };
};

const createConversationControllerUiTaskHandler = (host: ChatConversationListActionsHost, operationId: string, action: (controller: ChatConversationActionsControllerContract) => Promise<void> | void): ChatActionHandler => {
    return (): void => {
        runConversationControllerUiTask(host, operationId, action);
    };
};

const resolveTitleUiTaskHandlers = (host: ChatConversationListActionsHost): Record<typeof CHAT_ACTIONS.START_CONVERSATION_TITLE_EDIT | typeof CHAT_ACTIONS.CONVERSATION_TITLE_SAVE | typeof CHAT_ACTIONS.CONVERSATION_LIST_TITLE_SAVE, ChatActionHandler> => {
    return {
        [CHAT_ACTIONS.START_CONVERSATION_TITLE_EDIT]: createConversationControllerUiTaskHandler(host, 'chat:startConversationTitleEdit', (controller) => controller.startCurrentConversationTitleEdit()),
        [CHAT_ACTIONS.CONVERSATION_TITLE_SAVE]: createConversationControllerUiTaskHandler(host, 'chat:conversationTitleSave', (controller) => controller.handleConversationTitleSave()),
        [CHAT_ACTIONS.CONVERSATION_LIST_TITLE_SAVE]: createConversationControllerUiTaskHandler(host, 'chat:conversationListTitleSave', (controller) => controller.handleConversationListTitleSave())
    };
};

const createChatConversationListActionHandlers = (host: ChatConversationListActionsHost): Record<ChatConversationListActionId, ChatActionHandler> => {
    const titleUiTaskHandlers = resolveTitleUiTaskHandlers(host);
    return {
        [CHAT_ACTIONS.DELETE_CONVERSATION]: createStoppedPropagationConversationItemActionHandler(host, (_actionElement: HTMLElement, conversationId: string) => {
            runConversationControllerAction(host, (controller) => controller.deleteConversationById(conversationId));
        }),
        [CHAT_ACTIONS.EXPORT_CONVERSATION_ITEM]: createStoppedPropagationConversationItemActionHandler(host, (_actionElement: HTMLElement, conversationId: string) => {
            if (host.conversation.isExecuting(conversationId)) {
                return;
            }
            host.presentation.hideColorPicker();
            host.conversation.export(conversationId);
        }),
        [CHAT_ACTIONS.OPEN_CONVERSATION_COLOR_PICKER]: createStoppedPropagationConversationItemActionHandler(host, (actionElement: HTMLElement, conversationId: string) => {
            if (host.presentation.activeColorPickerConversationId() === conversationId) {
                host.presentation.hideColorPicker();
                return;
            }
            host.presentation.showColorPicker(actionElement, conversationId);
        }),
        [CHAT_ACTIONS.TOGGLE_CURRENT_CONVERSATION_FAVORITE]: (actionElement: HTMLElement) => {
            const conversationId = requireCurrentConversationId(host);
            runConversationControllerAction(host, (controller) => controller.toggleConversationFavoriteById(conversationId, actionElement));
        },
        [CHAT_ACTIONS.SWITCH_CONVERSATION]: (actionElement: HTMLElement, event: Event) => {
            if (shouldSkipConversationSwitch(event)) {
                return;
            }
            const conversationId = requireConversationItemId(host, actionElement);
            if (host.toolbar.selectionActive()) {
                host.toolbar.toggleSelection(conversationId);
                return;
            }
            runConversationControllerAction(host, (controller) => {
                controller.switchConversationById(conversationId);
                controller.collapseSidebarIfNarrowViewport();
            });
        },
        [CHAT_ACTIONS.START_CONVERSATION_RENAME]: createStoppedPropagationConversationItemActionHandler(host, (_actionElement: HTMLElement, conversationId: string) => {
            host.presentation.hideColorPicker();
            runConversationControllerUiTask(host, 'chat:startConversationRename', (controller) => controller.startConversationRenameById(conversationId));
        }),
        [CHAT_ACTIONS.START_CONVERSATION_TITLE_EDIT]: titleUiTaskHandlers[CHAT_ACTIONS.START_CONVERSATION_TITLE_EDIT],
        [CHAT_ACTIONS.CONVERSATION_TITLE_SAVE]: titleUiTaskHandlers[CHAT_ACTIONS.CONVERSATION_TITLE_SAVE],
        [CHAT_ACTIONS.CONVERSATION_TITLE_CANCEL]: withStoppedPropagation(createConversationControllerAction(host, (controller) => controller.handleConversationTitleCancel())),
        [CHAT_ACTIONS.CONVERSATION_LIST_TITLE_SAVE]: titleUiTaskHandlers[CHAT_ACTIONS.CONVERSATION_LIST_TITLE_SAVE],
        [CHAT_ACTIONS.CONVERSATION_LIST_TITLE_CANCEL]: withStoppedPropagation(createConversationControllerAction(host, (controller) => controller.handleConversationListTitleCancel()))
    };
};

export { createChatConversationListActionHandlers };
