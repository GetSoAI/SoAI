/* SoAI - Chat message sending ownership [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/ChatMessageSendingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationExecutionRunResult } from '@core/chat/protocols.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { normalizeFolderUploadFiles, resolveUploadFilesFromEvent, type ChatContentSegment, type SoaiPathDraftRecord } from '@features/chat/public.ts';
import { exportConversation } from '@pages/chat/controllers/chatmessagesendingcontroller/conversationExportController.ts';
import { handleAttachmentUploadFiles, handleAttachmentUploadFromEvent } from '@pages/chat/controllers/chatmessagesendingcontroller/attachmentUploadEventController.ts';
import { ConversationSendLockManager } from '@pages/chat/controllers/chatmessagesendingcontroller/ConversationSendLockManager.ts';
import { runWithConversationSendLockIfIdle, sendConversationInputFromComposer, sendMessageFromComposer, sendMessageFromPayload, sendQueuedTextMessage } from '@pages/chat/controllers/chatmessagesendingcontroller/sendMessageFlowController.ts';
import { refreshComposerState, resolveCurrentConversationSelection } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';
import { resolveEffectiveModelsForChatModelControl } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlStateManager.ts';
import { ChatRagAttachmentSession } from '@pages/chat/controllers/chatmessagesendingcontroller/ChatRagAttachmentSession.ts';
import { resolveComposerSoaiLinksFromInput } from '@pages/chat/controllers/chatmessagesendingcontroller/soaiLinkInputController.ts';
import type { AttachmentManager, ChatMessageSendingPort, ChatStreamingController, ConversationManager, MessageSendingHost, ConversationInputComposerOutcome, QueuedSendGuardContext, QueuedSendGuardResult, QueuedSendOutcome, SendMessageOptions, StorageManager } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

class ChatMessageSendingController implements ChatMessageSendingPort {
    #host: MessageSendingHost;
    #sendLocks = new ConversationSendLockManager();
    readonly rag: ChatRagAttachmentSession;
    #disposed = false;

    constructor(host: MessageSendingHost) {
        this.#host = host;
        this.rag = new ChatRagAttachmentSession(host);
    }

    hasPendingAttachmentProcessing(): boolean {
        this.#requireActive();
        return this.#host.services.getAttachmentManager().hasPendingAttachmentProcessing();
    }
    async sendMessage(options: SendMessageOptions = {}): Promise<void> {
        this.#requireActive();
        await this.#ensureInitialized();
        await sendMessageFromComposer({
            host: this.#host,
            manager: this.#sendLocks,
            onEffectiveSendCommitted: options.onEffectiveSendCommitted,
            afterAdmission: (conversationId) => this.rag.clearKnowledgeDraftCache(conversationId)
        });
    }

    async sendTextMessage(text: string, attachmentContent: readonly ChatContentSegment[] = []): Promise<void> {
        this.#requireActive();
        await this.#ensureInitialized();
        const messageText = toTrimmedString(text);
        if (!messageText && attachmentContent.length === 0) {
            return;
        }
        await sendMessageFromPayload({
            host: this.#host,
            manager: this.#sendLocks,
            payload: {
                messageText,
                sourceText: messageText,
                attachmentContent: [...attachmentContent],
                attachments: [],
                draftRevision: null
            },
            afterAdmission: (conversationId) => this.rag.clearKnowledgeDraftsAndRender(conversationId)
        });
    }

    async sendQueuedTextMessage(text: string, attachmentContent: readonly ChatContentSegment[], signal: AbortSignal, beforeSend: (context: QueuedSendGuardContext) => QueuedSendGuardResult): Promise<QueuedSendOutcome> {
        this.#requireActive();
        await this.#ensureInitialized();
        return await sendQueuedTextMessage({
            host: this.#host,
            manager: this.#sendLocks,
            text,
            attachmentContent,
            signal,
            beforeSend,
            afterAdmission: (conversationId) => this.rag.clearKnowledgeDraftsAndRender(conversationId)
        });
    }

    async resolveSoaiLinksFromInput(input: HTMLTextAreaElement, inputValue: string): Promise<void> {
        this.#requireActive();
        await this.#ensureInitialized();
        await resolveComposerSoaiLinksFromInput(this.#host, input, inputValue);
    }

    async runConversationExecutionIfIdle(conversationId: string, task: () => Promise<void>): Promise<ConversationExecutionRunResult> {
        this.#requireActive();
        return await runWithConversationSendLockIfIdle({
            manager: this.#sendLocks,
            conversationId,
            task: async () => {
                const signal = this.#host.platform.getRuntimeAbortSignal();
                await this.#host.services.getChatStreamingController().waitForTerminalReconciliation(conversationId, signal);
                await task();
            },
            canReleaseBusyLock: () => this.#canReleaseBusyConversationLock()
        });
    }

    #canReleaseBusyConversationLock(): boolean {
        const conversation = this.#host.conversation.getCurrentConversation();
        if (conversation === null) {
            return true;
        }
        return !this.#host.services.getChatStreamingController().isStreamingConversation(conversation.id);
    }

    async queueConversationInputFromComposer(intent: 'queued' | 'steer'): Promise<ConversationInputComposerOutcome> {
        this.#requireActive();
        await this.#ensureInitialized();
        return await sendConversationInputFromComposer({
            host: this.#host,
            manager: this.#sendLocks,
            intent: intent === 'steer' ? 'steer' : 'prompt',
            afterAdmission: (conversationId) => this.rag.clearKnowledgeDraftsAndRender(conversationId)
        });
    }

    async steerActiveStream(): Promise<ConversationInputComposerOutcome> {
        this.#requireActive();
        await this.#ensureInitialized();
        const effective = resolveEffectiveModelsForChatModelControl({
            conversation: this.#host.conversation.getCurrentConversation(),
            fallbackModelId: this.#host.model.getCurrentModel()
        });
        return await sendConversationInputFromComposer({
            host: this.#host,
            manager: this.#sendLocks,
            intent: effective.comparison.length > 0 ? 'prompt' : 'steer',
            afterAdmission: (conversationId) => this.rag.clearKnowledgeDraftsAndRender(conversationId)
        });
    }

    async removeAttachedFile(fileId: string): Promise<void> {
        this.#requireActive();
        await this.#ensureInitialized();
        const attachmentManager = this.#host.services.getAttachmentManager();
        const materializeRecord = (record: SoaiPathDraftRecord): void => this.#host.services.getSoaiLinkResolutionManager().materializeRecord(record);
        await attachmentManager.removeAttachedFile(fileId, materializeRecord);
        refreshComposerState(this.#host, { updateInputState: false });
    }
    async removeDraftKnowledgeAttachment(knowledgeAttachmentId: string): Promise<void> {
        this.#requireActive();
        const selection = resolveCurrentConversationSelection(this.#host);
        if (!selection) return;
        const summary = await this.#host.services.getChatApi().webui.chat.attachments.knowledge.delete(selection.conversationId, knowledgeAttachmentId);
        this.rag.handleKnowledgeChanged(summary);
    }

    exportConversation(conversationId: string | null): void {
        this.#requireActive();
        this.#host.platform
            .runWithBoundary('chat:exportConversationInitialize', async () => {
                await this.#ensureInitialized();
                exportConversation(this.#host, conversationId);
            })
            .catch((error: Error) => this.#host.platform.handleError(error, 'Chat export initialization failed'));
    }

    async handleFileUpload(event: Event): Promise<void> {
        this.#requireActive();
        await this.#ensureInitialized();
        await handleAttachmentUploadFromEvent(this.#host, event, 'picker');
    }

    async handleSelectedUploadFiles(files: File[]): Promise<void> {
        this.#requireActive();
        await this.#ensureInitialized();
        await handleAttachmentUploadFiles(this.#host, files, 'picker');
    }

    async handleCameraCaptureFile(file: File): Promise<void> {
        this.#requireActive();
        await this.#ensureInitialized();
        await handleAttachmentUploadFiles(this.#host, [file], 'camera');
    }

    async handleFolderUpload(event: Event): Promise<void> {
        this.#requireActive();
        await this.#ensureInitialized();
        await this.handleSelectedFolderUploadFiles(resolveUploadFilesFromEvent(event));
    }

    async handleSelectedFolderUploadFiles(files: File[]): Promise<void> {
        this.#requireActive();
        await this.#ensureInitialized();
        await handleAttachmentUploadFiles(this.#host, normalizeFolderUploadFiles(files), 'folder');
    }

    dispose(): void {
        if (this.#disposed) {
            return;
        }
        this.#disposed = true;
        this.#sendLocks.clear();
        this.rag.dispose();
    }

    #ensureInitialized(): Promise<void> {
        return this.#host.platform.ensureManagersInitialized(this);
    }

    #requireActive(): void {
        if (this.#disposed) {
            throw new Error('Chat message sending controller has been disposed');
        }
    }
}

export type { MessageSendingHost, AttachmentManager, StorageManager, ChatStreamingController, ConversationManager, ConversationExecutionRunResult };
export { ChatMessageSendingController };
export interface ChatMessageSendingOwner {
    messageSending: ChatMessageSendingPort;
}
