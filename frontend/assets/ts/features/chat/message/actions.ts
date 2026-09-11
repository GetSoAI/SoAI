/* SoAI - Chat feature message actions [frontend/assets/ts/features/chat/message/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { dom } from '@core/dom/dom.ts';
import { isString } from '@core/typeGuards.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatMessageActionData, ChatMessageActionsDependencies } from '@features/chat/message/actionDeps.ts';
import { removeCompactionBoundary } from '@features/chat/message/contextcompaction/boundaryRemovalAction.ts';
import { isContextCompactionBoundaryMessage, resolveContextCompactionRegenerationTimestamp } from '@features/chat/message/contextcompaction/detection.ts';
import { stopShell } from '@features/chat/message/shell/stopAction.ts';
import { openMessageAttachmentOverflow } from '@features/chat/message/messageAttachmentOverflowAction.ts';
import { copyMessageText, copyTimestamp, type ChatMessageCopyDependencies } from '@features/chat/message/messageActionsCopy.ts';
import { isStreamingBlockedMessageAction } from '@features/chat/message/messageActionStreamingPolicy.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { ChatMessageEditController } from '@features/chat/message/messageEditController.ts';
import type { ChatMessageMutationDependencies } from '@features/chat/message/messageMutationControllerContracts.ts';
import { setRegenerateButtonLoading } from '@features/chat/message/messageRegenerateButton.ts';
import { ChatMessageRegenerationController } from '@features/chat/message/messageRegenerationController.ts';
import { revealRunningActivity } from '@features/chat/message/runningActivityRevealAction.ts';
import { isAssistantMessageRole, isUserMessageRole } from '@features/chat/message/messageRole.ts';
import { toggleLoadingActivityItem } from '@features/chat/message/loadingActivityToggle.ts';
import { SpeakActionController } from '@features/chat/message/speakActionController.ts';

const createCopyDependencies = (dependencies: ChatMessageActionsDependencies): ChatMessageCopyDependencies => ({
    resolveMessageContentSegments: (message) => dependencies.presentation.resolveMessageContentSegments(message),
    runWithBoundary: (name, functionValue) => dependencies.interaction.runWithBoundary(name, functionValue),
    hasClipboardSupport: () => dependencies.interaction.hasClipboardSupport(),
    copyToClipboard: (text, options) => dependencies.interaction.copyToClipboard(text, options),
    showNotification: (message, type) => dependencies.interaction.showNotification(message, type)
});

const createMessageMutationSharedDependencies = (dependencies: ChatMessageActionsDependencies): ChatMessageMutationDependencies => ({
    getCurrentConversation: () => dependencies.session.getCurrentConversation(),
    getCurrentModel: () => dependencies.session.getCurrentModel(),
    getModelStreamHasPayload: () => dependencies.session.getModelStreamHasPayload(),
    isModelAvailable: (modelId) => dependencies.session.isModelAvailable(modelId),
    runWithBoundary: (name, functionValue) => dependencies.interaction.runWithBoundary(name, functionValue),
    saveAndSync: (conversation) => dependencies.runtime.saveAndSync(conversation),
    loadConversationMessages: (conversationId, options) => dependencies.runtime.loadConversationMessages(conversationId, options),
    streamResponse: (conversation, options) => dependencies.runtime.streamResponse(conversation, options),
    runConversationExecutionIfIdle: (conversationId, task) => dependencies.runtime.runConversationExecutionIfIdle(conversationId, task),
    invalidateChatMarkup: (scope) => dependencies.runtime.invalidateChatMarkup(scope),
    renderCurrentConversation: () => dependencies.runtime.renderCurrentConversation(),
    refreshConversationsUI: () => dependencies.runtime.refreshConversationsUI(),
    isConversationExecuting: (conversationId) => dependencies.runtime.isConversationExecuting(conversationId),
    reportRequestFailure: (error) => dependencies.runtime.reportRequestFailure(error)
});

class ChatMessageActions {
    #dependencies: ChatMessageActionsDependencies;
    readonly #speakActionController: SpeakActionController;
    readonly #editController: ChatMessageEditController;
    readonly #regenerationController: ChatMessageRegenerationController;
    readonly #runningActivityRevealOperations = new Map<string, Promise<void>>();

    constructor(dependencies: ChatMessageActionsDependencies) {
        this.#dependencies = dependencies;
        this.#speakActionController = new SpeakActionController({
            resolveMessageContainer: (messageId) => this.#dependencies.presentation.resolveMessageContainer(messageId),
            speakText: (text, options) => this.#dependencies.runtime.speakText(text, options),
            stopSpeaking: () => this.#dependencies.runtime.stopSpeaking(),
            runWithBoundary: (name, functionValue) => this.#dependencies.interaction.runWithBoundary(name, functionValue),
            showNotification: (message, type) => this.#dependencies.interaction.showNotification(message, type)
        });
        this.#editController = new ChatMessageEditController({
            view: {
                domChangeTarget: this.#dependencies.presentation.domChangeTarget,
                getIcon: (name, options) => this.#dependencies.presentation.getIcon(name, options),
                renderMessageTextContent: (message) => this.#dependencies.presentation.renderMessageTextContent(message),
                resolveMessageContainer: (messageId) => this.#dependencies.presentation.resolveMessageContainer(messageId),
                postRender: (container) => this.#dependencies.presentation.postRender(container)
            },
            ...createMessageMutationSharedDependencies(this.#dependencies),
            resolveMessageReference: (conversation, messageId) => this.#dependencies.presentation.resolveMessageReference(conversation, messageId),
            resubmitUserMessage: (conversation, inputArguments) => this.#dependencies.runtime.resubmitUserMessage(conversation, inputArguments),
            commitPendingDeletesForConversation: (conversation) => this.#dependencies.runtime.commitPendingDeletesForConversation(conversation)
        });
        this.#regenerationController = new ChatMessageRegenerationController({
            ...createMessageMutationSharedDependencies(this.#dependencies),
            truncateMessagesFromCursor: (conversation, inputArguments) => this.#dependencies.runtime.truncateMessagesFromCursor(conversation, inputArguments)
        });
    }

    dispose(): void {
        this.#speakActionController.dispose();
        this.#editController.dispose();
        this.#runningActivityRevealOperations.clear();
    }

    #isCurrentConversationActionBlocked(): boolean {
        const conversation = this.#dependencies.session.getCurrentConversation();
        if (!conversation) {
            return false;
        }
        const conversationId = conversation.id;
        if (typeof conversationId !== 'string' || !conversationId) {
            return false;
        }
        if (!this.#dependencies.runtime.isConversationExecuting(conversationId)) {
            return false;
        }
        return this.#dependencies.runtime.isChatStreamingConversation(conversationId);
    }

    #isEditableUserMessage(message: ChatMessage, index: number): boolean {
        return isUserMessageRole(message) && index >= 0;
    }

    async handleMessageAction(messageId: string, action: string | null | undefined, data?: ChatMessageActionData): Promise<void> {
        if (!isString(messageId)) {
            return;
        }
        const normalizedMessageId = normalizeMessageDomId(messageId);
        if (!normalizedMessageId) {
            return;
        }
        await this.#executeAction(normalizedMessageId, action, data);
    }

    async #executeAction(messageId: string, action: string | null | undefined, data?: ChatMessageActionData): Promise<void> {
        const conversation = this.#dependencies.session.getCurrentConversation();
        if (!conversation) {
            return;
        }
        if (isStreamingBlockedMessageAction(action) && this.#isCurrentConversationActionBlocked()) {
            return;
        }

        const { index, message } = this.#dependencies.presentation.resolveMessageReference(conversation, messageId);
        if (!message) {
            return;
        }

        switch (action) {
            case CHAT_ACTIONS.COPY:
                await copyMessageText(createCopyDependencies(this.#dependencies), message);
                break;
            case CHAT_ACTIONS.COPY_TIMESTAMP:
                if (data?.timestamp) {
                    await copyTimestamp(createCopyDependencies(this.#dependencies), data.timestamp);
                }
                break;
            case CHAT_ACTIONS.REGENERATE:
                if (isAssistantMessageRole(message) && index >= 0) {
                    const container = this.#dependencies.presentation.resolveMessageContainer(messageId);
                    let loadingToken: string | null = null;
                    if (container) {
                        const button = dom.resolve('.regenerate-message-btn', container);
                        if (button instanceof HTMLButtonElement) {
                            loadingToken = setRegenerateButtonLoading(button, true);
                        }
                    }
                    try {
                        if (isContextCompactionBoundaryMessage(message)) {
                            const assistantTurnAtMs = resolveContextCompactionRegenerationTimestamp(message);
                            if (assistantTurnAtMs === null) {
                                this.#dependencies.interaction.showNotification(i18n.t('chat.agent.compact.failed'), 'error');
                                return;
                            }
                            await this.#dependencies.runtime.regenerateCompactionInCurrentConversation(assistantTurnAtMs);
                            return;
                        }
                        await this.#regenerationController.regenerateMessage(index);
                    } finally {
                        if (container && loadingToken) {
                            const button = dom.resolve('.regenerate-message-btn', container);
                            if (button instanceof HTMLButtonElement) {
                                setRegenerateButtonLoading(button, false, loadingToken);
                            }
                        }
                    }
                }
                break;
            case CHAT_ACTIONS.INFO:
                if (isAssistantMessageRole(message)) {
                    this.#dependencies.interaction.showMessageModal(message);
                }
                break;
            case CHAT_ACTIONS.OPEN_ATTACHMENT_OVERFLOW:
                openMessageAttachmentOverflow(
                    {
                        resolveMessageContentSegments: (candidateMessage) => this.#dependencies.presentation.resolveMessageContentSegments(candidateMessage),
                        showAttachmentOverflowModal: (inputArguments) => this.#dependencies.interaction.showAttachmentOverflowModal(inputArguments)
                    },
                    conversation,
                    message,
                    data?.knowledgeAttachmentId
                );
                break;
            case CHAT_ACTIONS.REMOVE_COMPACTION_BOUNDARY:
                if (isAssistantMessageRole(message)) {
                    await removeCompactionBoundary(this.#dependencies, conversation, data);
                }
                break;
            case CHAT_ACTIONS.STOP_SHELL:
                if (isAssistantMessageRole(message)) {
                    await stopShell(this.#dependencies, conversation, data);
                }
                break;
            case CHAT_ACTIONS.TOGGLE_LOADING_ACTIVITY_ITEM:
                if (isAssistantMessageRole(message)) {
                    toggleLoadingActivityItem(this.#dependencies, messageId);
                }
                break;
            case CHAT_ACTIONS.REVEAL_RUNNING_ACTIVITY:
                if (isAssistantMessageRole(message)) {
                    await revealRunningActivity(this.#dependencies, this.#runningActivityRevealOperations, messageId, message, data);
                }
                break;
            case CHAT_ACTIONS.SPEAK:
                if (isAssistantMessageRole(message)) {
                    await this.#speakActionController.handleSpeakAction(messageId);
                }
                break;
            case CHAT_ACTIONS.RESEND:
                if (this.#isEditableUserMessage(message, index)) {
                    await this.#editController.resendMessage(messageId);
                }
                break;
            case CHAT_ACTIONS.EDIT:
                if (!this.#isEditableUserMessage(message, index)) {
                    return;
                }
                this.#editController.beginEditing(message, messageId);
                break;
            case CHAT_ACTIONS.EDIT_CANCEL:
                if (!this.#isEditableUserMessage(message, index)) {
                    return;
                }
                this.#editController.endEditing(message, messageId);
                break;
            case CHAT_ACTIONS.EDIT_SAVE:
                if (!this.#isEditableUserMessage(message, index)) {
                    return;
                }
                await this.#editController.requestSave();
                break;
            case CHAT_ACTIONS.DELETE:
                if (index < 0) {
                    return;
                }
                await this.#dependencies.interaction.runWithBoundary('chat:deleteMessageRequest', async () => {
                    await this.#dependencies.interaction.requestMessageDelete(conversation, messageId);
                });
                break;
            case CHAT_ACTIONS.DELETE_UNDO:
                if (index < 0) {
                    return;
                }
                await this.#dependencies.interaction.runWithBoundary('chat:deleteMessageUndo', async () => {
                    await this.#dependencies.interaction.undoMessageDelete(conversation, messageId);
                });
                break;
            case CHAT_ACTIONS.DELETE_NOW:
                if (index < 0) {
                    return;
                }
                await this.#dependencies.interaction.runWithBoundary('chat:deleteMessageNow', async () => {
                    await this.#dependencies.interaction.commitMessageDeleteNow(conversation, messageId);
                });
                break;
            default:
                break;
        }
    }
}

export { ChatMessageActions };
