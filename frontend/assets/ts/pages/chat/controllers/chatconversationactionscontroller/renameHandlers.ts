/* SoAI - Chat page rename handlers [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/renameHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { focusAndSelectInlineTextEditInput } from '@core/ui/inlineedit/controller.ts';
import { resolveConversationDisplayTitleFromConversation, type Conversation } from '@features/chat/public.ts';
import { cancelConversationRename, startConversationRenameSession, updateConversationRenameDraft } from '@pages/chat/controllers/chatconversationactionscontroller/service.ts';
import type { ChatConversationActionsControllerRuntime } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';

const resolveRenameDraftTitle = (conversation: Conversation): string => resolveConversationDisplayTitleFromConversation(conversation, i18n.t('chat.conversation.untitled'));

const startConversationRenameById = async (runtime: ChatConversationActionsControllerRuntime, conversationId: string): Promise<void> => {
    const conversation = runtime.state.getConversation(conversationId);
    if (!conversation) {
        return;
    }
    await cancelConversationRename(runtime.host, runtime.state);
    await startConversationRenameSession(runtime.host, runtime.state, 'sidebar', conversationId, resolveRenameDraftTitle(conversation));
    const input = runtime.host.view.getConversationListTitleInputElement();
    if (input) {
        focusAndSelectInlineTextEditInput(input);
    }
};

const startCurrentConversationTitleEdit = async (runtime: ChatConversationActionsControllerRuntime): Promise<void> => {
    const conversation = runtime.host.view.getCurrentConversation();
    if (!conversation) {
        return;
    }
    await cancelConversationRename(runtime.host, runtime.state);
    await startConversationRenameSession(runtime.host, runtime.state, 'header', conversation.id, resolveRenameDraftTitle(conversation));
    const input = runtime.host.view.getConversationTitleInputElement();
    if (input) {
        focusAndSelectInlineTextEditInput(input);
    }
};

const cancelConversationRenameOnBlur = async (runtime: ChatConversationActionsControllerRuntime, event: Event, ignoreSelector: string): Promise<void> => {
    const relatedTarget = typeof FocusEvent === 'function' && event instanceof FocusEvent ? event.relatedTarget : null;
    const related = relatedTarget instanceof Element ? relatedTarget : null;
    if (related?.matches(ignoreSelector)) {
        return;
    }
    await cancelConversationRename(runtime.host, runtime.state);
};

const createConversationTitleCancelHandler = (getInput: (runtime: ChatConversationActionsControllerRuntime) => HTMLInputElement | null, errorLabel: string): ((runtime: ChatConversationActionsControllerRuntime) => void) => {
    return (runtime: ChatConversationActionsControllerRuntime): void => {
        void cancelConversationRename(runtime.host, runtime.state).catch((error) => {
            runtime.host.workflow.handleError?.(error, errorLabel);
        });
        getInput(runtime)?.blur();
    };
};

const handleConversationTitleCancel = createConversationTitleCancelHandler((runtime) => runtime.host.view.getConversationTitleInputElement(), 'Chat conversation title cancel failed');

const handleConversationListTitleCancel = createConversationTitleCancelHandler((runtime) => runtime.host.view.getConversationListTitleInputElement(), 'Chat conversation list title cancel failed');

const updateConversationRenameDraftValue = (runtime: ChatConversationActionsControllerRuntime, value: string): void => {
    updateConversationRenameDraft(runtime.host, runtime.state, value);
};

export { cancelConversationRenameOnBlur, handleConversationListTitleCancel, handleConversationTitleCancel, startConversationRenameById, startCurrentConversationTitleEdit, updateConversationRenameDraftValue };
