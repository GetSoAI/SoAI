/* SoAI - Chat conversation actions controller service [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { limitConversationTitleLength, sanitizeTitle } from '@features/chat/public.ts';
import type { ConversationActionsHost, ConversationActionsStateAccess, ConversationManager, StorageManager } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';
import type { ChatConversationRenameScope } from '@pages/chat/state/chatConversationRenameState.ts';

const runConversationActionOperation = async (options: { host: ConversationActionsHost; scope: string; task: () => Promise<void>; logMessage: string; errorMessage: string; shouldNotifyError?: () => boolean }): Promise<void> => {
    try {
        await options.host.workflow.runWithBoundary(options.scope, options.task);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('ChatPage', options.logMessage, runtimeError);
        if (options.shouldNotifyError === undefined || options.shouldNotifyError()) {
            options.host.workflow.feedback.show(options.errorMessage || i18n.t('common.error'), 'error');
        }
    }
};

const renderConversationRenameScope = async (host: ConversationActionsHost, scope: ChatConversationRenameScope): Promise<void> => {
    if (scope === 'header') {
        await host.view.renderCurrentConversation();
        return;
    }
    await host.view.renderConversationList();
};

const startConversationRenameSession = async (host: ConversationActionsHost, state: ConversationActionsStateAccess, scope: ChatConversationRenameScope, conversationId: string, title: string): Promise<void> => {
    const cappedTitle = limitConversationTitleLength(title);
    state.setConversationRenameState({
        scope,
        conversationId,
        originalTitle: title,
        draft: cappedTitle
    });
    host.workflow.notifySaveChanged();
    await renderConversationRenameScope(host, scope);
};

const updateConversationRenameDraft = (host: ConversationActionsHost, state: ConversationActionsStateAccess, draft: string): void => {
    const renameState = state.getConversationRenameState();
    if (!renameState) {
        return;
    }
    state.setConversationRenameState({
        ...renameState,
        draft: limitConversationTitleLength(draft)
    });
    host.workflow.notifySaveChanged();
};

const cancelConversationRename = async (host: ConversationActionsHost, state: ConversationActionsStateAccess): Promise<void> => {
    const renameState = state.getConversationRenameState();
    if (!renameState) {
        return;
    }
    state.setConversationRenameState(null);
    host.workflow.notifySaveChanged();
    await renderConversationRenameScope(host, renameState.scope);
};

const cancelConversationRenameState = (host: ConversationActionsHost, state: ConversationActionsStateAccess): void => {
    if (state.getConversationRenameState() === null) return;
    state.setConversationRenameState(null);
    host.workflow.notifySaveChanged();
};

const persistConversationRename = async (host: ConversationActionsHost, state: ConversationActionsStateAccess, conversationManager: ConversationManager, storageManager: StorageManager): Promise<void> => {
    const renameState = state.getConversationRenameState();
    if (!renameState) {
        return;
    }
    const sanitized = sanitizeTitle(limitConversationTitleLength(renameState.draft));
    await conversationManager.updateConversationTitle(renameState.conversationId, sanitized);
    state.setConversationRenameState(null);
    host.workflow.notifySaveChanged();
    storageManager.saveChatState();
    await host.view.refreshConversationsUI();
};

export { cancelConversationRename, cancelConversationRenameState, persistConversationRename, runConversationActionOperation, startConversationRenameSession, updateConversationRenameDraft };
