/* SoAI - Chat send recovery and rollback controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/sendFlowRecoveryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { restoreConversationMutationSnapshot, type ConversationMutationSnapshot } from '@features/chat/public.ts';
import { blockQueuedSend } from '@pages/chat/controllers/chatmessagesendingcontroller/constants.ts';
import { refreshComposerState, restoreComposerInput } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';
import type { Conversation, MessageSendingHost, QueuedSendOutcome } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

const isWorkspaceScopeChangedError = (error: Error): boolean => {
    const normalized = error.message.trim().toLowerCase();
    return normalized.includes('workspace scope changed') || normalized.includes('conversation workspace path') || normalized.includes('conversation folder override');
};

const restoreComposerForUnpersistedPayload = (inputArguments: { host: MessageSendingHost; conversationId: string; composerTextForClearing: string; didPrepareComposerSurface: boolean; didClearComposerInput: boolean; didPersistConversation: boolean }): void => {
    if (inputArguments.didPersistConversation || inputArguments.host.conversation.getCurrentConversation()?.id !== inputArguments.conversationId) {
        return;
    }
    if (inputArguments.didClearComposerInput) {
        restoreComposerInput(inputArguments.host, inputArguments.composerTextForClearing);
    }
    if (inputArguments.didPrepareComposerSurface) {
        inputArguments.host.presentation.renderAttachedFilesPreview();
    }
    refreshComposerState(inputArguments.host);
};

const blockSendForConversationMismatch = (inputArguments: { host: MessageSendingHost; conversation: Conversation; mutationSnapshot: ConversationMutationSnapshot; restoreConversation: boolean; workspaceCurrent: boolean }): QueuedSendOutcome => {
    if (inputArguments.restoreConversation) {
        restoreConversationMutationSnapshot(inputArguments.conversation, inputArguments.mutationSnapshot);
    }
    refreshComposerState(inputArguments.host);
    if (!inputArguments.workspaceCurrent) {
        inputArguments.host.platform.feedback.show(i18n.t('chat.errors.soaiWorkspaceChanged'), 'error');
    }
    return blockQueuedSend('conversation-mismatch');
};

const recoverFailedSendSurface = async (inputArguments: { host: MessageSendingHost; conversation: Conversation; conversationId: string; mutationSnapshot: ConversationMutationSnapshot; restoreConversation: boolean; composerTextForClearing: string; didPrepareComposerSurface: boolean; didClearComposerInput: boolean; didPersistConversation: boolean }): Promise<void> => {
    restoreComposerForUnpersistedPayload({
        host: inputArguments.host,
        conversationId: inputArguments.conversationId,
        composerTextForClearing: inputArguments.composerTextForClearing,
        didPrepareComposerSurface: inputArguments.didPrepareComposerSurface,
        didClearComposerInput: inputArguments.didClearComposerInput,
        didPersistConversation: inputArguments.didPersistConversation
    });
    if (inputArguments.restoreConversation) {
        restoreConversationMutationSnapshot(inputArguments.conversation, inputArguments.mutationSnapshot);
    }
    refreshComposerState(inputArguments.host);
    if (inputArguments.host.conversation.getCurrentConversation()?.id !== inputArguments.conversationId) {
        return;
    }
    inputArguments.host.presentation.invalidateChatMarkup('current');
    try {
        await inputArguments.host.presentation.renderCurrentConversation();
    } catch (error) {
        inputArguments.host.platform.handleError(ensureError(error), i18n.t('chat.errors.syncFailed'), { notify: true });
    }
};

export { blockSendForConversationMismatch, isWorkspaceScopeChangedError, recoverFailedSendSurface, restoreComposerForUnpersistedPayload };
