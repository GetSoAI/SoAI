/* SoAI - Shared composer send effects and payload resolution [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isChatAttachmentReadyForSend, isChatConversationSettingsWritable, normalizeConversationId, resolvePrimaryModelIdForExecution, type ChatAttachment, type ChatContentSegment, type Conversation } from '@features/chat/public.ts';
import { hasClaimableDraftKnowledgeAttachment } from '@pages/chat/controllers/chatmessagesendingcontroller/knowledgeAttachmentDraftManager.ts';
import type { MessageSendingHost } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

interface ComposerInputHost {
    composer: {
        getChatInput(): HTMLTextAreaElement | null;
        setUIValue(element: Element, value: string, options?: { attribute?: string }): void;
        resizeChatInput(element: Element): void;
        noteChatInputDraftChanged(value: string): void;
    };
}

type ComposerPayload = {
    messageText: string;
    sourceText: string;
    attachmentContent: ChatContentSegment[];
    attachments: ChatAttachment[];
    draftRevision: number | null;
};

interface ConversationForSendResolution {
    conversation: Conversation;
    createdForSend: boolean;
}

const syncConversationSystemPromptLock = async (host: MessageSendingHost, conversationId: string, lockValue: string | null): Promise<void> => {
    const conversation = host.conversation.getCurrentConversation();
    if (!isChatConversationSettingsWritable(conversation) || conversation.id !== conversationId) {
        return;
    }
    try {
        await host.platform.runWithBoundary('chat:systemPromptLock', async () => {
            await host.services.getConversationManager().updateConversationSettings(conversationId, { prompts: { userSystemPrompt: lockValue } });
        });
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ChatPage', 'System prompt lock synchronization failed', runtimeError);
        host.platform.handleError(runtimeError, getChatSyncErrorTitle(), { notify: true });
        throw runtimeError;
    }
};

const refreshConversationListAfterSharedSync = async (host: MessageSendingHost): Promise<void> => {
    await host.presentation.refreshConversationsUI();
};

const clearComposerInput = (host: ComposerInputHost, expectedText?: string): boolean => {
    const input = host.composer.getChatInput();
    if (!(input instanceof HTMLTextAreaElement)) {
        return false;
    }
    if (expectedText !== undefined) {
        const currentText = readTrimmedInputValue(input);
        if (currentText !== expectedText.trim()) {
            return false;
        }
    }
    host.composer.setUIValue(input, '', { attribute: 'value' });
    host.composer.resizeChatInput(input);
    host.composer.noteChatInputDraftChanged('');
    return true;
};

const restoreComposerInput = (host: ComposerInputHost, text: string): void => {
    const input = host.composer.getChatInput();
    if (!(input instanceof HTMLTextAreaElement)) {
        return;
    }
    if (readTrimmedInputValue(input).length > 0) {
        return;
    }
    host.composer.setUIValue(input, text, { attribute: 'value' });
    host.composer.resizeChatInput(input);
    host.composer.noteChatInputDraftChanged(text);
};

const refreshComposerState = (host: MessageSendingHost, options: { updateInputState?: boolean } = {}): void => {
    host.presentation.updateEmptyStateInputHint();
    if (options.updateInputState === false) {
        return;
    }
    host.composer.updateInputState();
};

const hasKnowledgeDraftPayloadForSubmission = async (host: MessageSendingHost): Promise<boolean> => {
    const selection = resolveCurrentConversationSelection(host);
    if (!selection) {
        return false;
    }
    const payload = await host.platform.runWithBoundary('chat:listDraftKnowledgeAttachments', () => host.services.getChatApi().webui.chat.attachments.knowledge.draft(selection.conversationId, { previewLimit: 0, signal: host.platform.getRuntimeAbortSignal() ?? undefined }));
    return hasClaimableDraftKnowledgeAttachment(payload);
};

const resolveComposerPayloadForSubmission = async (host: MessageSendingHost): Promise<ComposerPayload | null> => {
    const messageText = readComposerInputText(host);
    const sourceText = readComposerSourceText(host);
    const attachmentManager = host.services.getAttachmentManager();
    const initialDraftRevision = attachmentManager.getDraftRevision();
    const initialAttachments = attachmentManager.getAttachments();
    const hasInitialKnowledgeDraft = hasComposerPayload(messageText, initialAttachments.length) ? false : await hasKnowledgeDraftPayloadForSubmission(host);
    if (!hasComposerPayload(messageText, initialAttachments.length, hasInitialKnowledgeDraft)) {
        return null;
    }
    await attachmentManager.waitForAttachments();
    if (attachmentManager.getDraftRevision() !== initialDraftRevision || readComposerInputText(host) !== messageText || readComposerSourceText(host) !== sourceText) {
        refreshComposerState(host);
        return null;
    }
    if (attachmentManager.hasPendingAttachmentProcessing()) {
        refreshComposerState(host);
        return null;
    }
    const attachments = [...attachmentManager.getAttachments()];
    const hasKnowledgeDraft = hasComposerPayload(messageText, attachments.length) ? false : await hasKnowledgeDraftPayloadForSubmission(host);
    if (attachmentManager.getDraftRevision() !== initialDraftRevision || readComposerInputText(host) !== messageText || readComposerSourceText(host) !== sourceText) {
        refreshComposerState(host);
        return null;
    }
    if (!hasComposerPayload(messageText, attachments.length, hasKnowledgeDraft)) {
        refreshComposerState(host);
        return null;
    }
    const failedAttachments = attachments.filter((attachment) => attachment.parseStatus === 'error');
    if (failedAttachments.length > 0) {
        host.platform.feedback.show(i18n.t('chat.attachments.removeFailedBeforeSend'), 'error');
        refreshComposerState(host);
        return null;
    }
    const notReadyAttachments = attachments.filter((attachment) => !isChatAttachmentReadyForSend(attachment));
    if (notReadyAttachments.length > 0) {
        host.platform.feedback.show(i18n.t('chat.attachments.notReadyToSend'), 'info');
        refreshComposerState(host);
        return null;
    }
    const attachmentContent = attachmentManager.buildContentFragmentsFromAttachments(attachments);
    return { messageText, sourceText, attachmentContent, attachments, draftRevision: attachmentManager.getDraftRevision() };
};

const resolveCurrentConversationSelection = (host: MessageSendingHost): { conversation: Conversation; conversationId: string } | null => {
    const conversation = host.conversation.getCurrentConversation();
    const conversationId = normalizeConversationId(conversation?.id);
    if (!conversation || !conversationId) {
        return null;
    }
    return { conversation, conversationId };
};

const requireCurrentConversationForSend = async (host: MessageSendingHost): Promise<ConversationForSendResolution> => {
    const currentSelection = resolveCurrentConversationSelection(host);
    if (currentSelection) {
        return { conversation: currentSelection.conversation, createdForSend: false };
    }
    const ensuredConversation = await host.platform.ensureConversationForSend();
    const ensuredSelection = resolveCurrentConversationSelection(host);
    if (!ensuredSelection) {
        throw new Error('Chat send requires an active conversation');
    }
    const ensuredConversationId = normalizeConversationId(ensuredConversation?.conversationId);
    const createdForSend = ensuredConversation?.created === true && ensuredConversationId === ensuredSelection.conversationId;
    return { conversation: ensuredSelection.conversation, createdForSend };
};

const readComposerInputText = (host: MessageSendingHost): string => {
    const input = host.composer.getChatInput();
    if (!(input instanceof HTMLTextAreaElement)) {
        return '';
    }
    return readTrimmedInputValue(input);
};

const readComposerSourceText = (host: MessageSendingHost): string => {
    const input = host.composer.getChatInput();
    if (!(input instanceof HTMLTextAreaElement)) return '';
    return host.services.getSoaiLinkResolutionManager().sourceForDisplayedText(input.value).trim();
};

const resolveSelectedSendModel = (host: MessageSendingHost): string | null => {
    const conversation = host.conversation.getCurrentConversation();
    return conversation ? resolvePrimaryModelIdForExecution({ selectedModelId: host.model.getCurrentModel(), conversation }) : null;
};

const hasComposerPayload = (messageText: string, attachmentCount: number, hasKnowledgeDraft: boolean = false): boolean => {
    return Boolean(messageText) || attachmentCount > 0 || hasKnowledgeDraft;
};

const isReadySendAttachment = (attachment: ChatAttachment): boolean => {
    return isChatAttachmentReadyForSend(attachment);
};

const getChatSyncErrorTitle = (): string => {
    return i18n.t('chat.errors.syncFailed');
};

const notifyIngestionStarted = (host: MessageSendingHost, count: number): void => {
    host.platform.feedback.show(i18n.t('chat.ingestion.started', { count }), 'info');
};

const notifyExportResult = (host: MessageSendingHost, hasMessages: boolean): boolean => {
    if (!hasMessages) {
        host.platform.feedback.show(i18n.t('chat.export.noMessages'), 'info');
        return false;
    }
    host.platform.feedback.show(i18n.t('chat.export.success'), 'download');
    return true;
};

export { clearComposerInput, getChatSyncErrorTitle, hasComposerPayload, isReadySendAttachment, notifyExportResult, notifyIngestionStarted, readComposerInputText, refreshComposerState, refreshConversationListAfterSharedSync, requireCurrentConversationForSend, resolveComposerPayloadForSubmission, resolveCurrentConversationSelection, resolveSelectedSendModel, restoreComposerInput, syncConversationSystemPromptLock };
export type { ComposerPayload };
