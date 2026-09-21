/* SoAI - Chat page composer action handlers [frontend/assets/ts/pages/chat/controllers/actionhandlers/core/composerActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { CHAT_ACTIONS } from '@features/chat/public.ts';
import { createCollapsedActionHandlers, createCollapsedElementActionHandler, createMappedActionHandlers, createPreventDefaultStoppedActionHandler, requireCurrentConversationId, runCollapsedUiTask } from '@pages/chat/controllers/actionhandlers/core/effects.ts';
import type { ChatActionHandler, ChatAttachmentActionPort, ChatAudioActionPort, ChatComposerActionPort, ChatConfigurationActionPort, ChatConversationActionPort, ChatExecutionActionPort, ChatPresentationActionPort, ChatRagActionPort, ChatSharedActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';
import { executeComposerPrimaryAction } from '@pages/chat/controllers/actionhandlers/core/composerPrimaryActionController.ts';
import { openChatAttachModal } from '@pages/chat/controllers/modals/chatattach/chatAttachModal.ts';

interface ChatComposerActionsHost {
    attachments: ChatAttachmentActionPort;
    audio: ChatAudioActionPort;
    composer: ChatComposerActionPort;
    configuration: ChatConfigurationActionPort;
    conversation: ChatConversationActionPort;
    execution: ChatExecutionActionPort;
    presentation: ChatPresentationActionPort;
    rag: ChatRagActionPort;
    shared: ChatSharedActionPort;
}

type ChatComposerActionId = typeof CHAT_ACTIONS.SEND_OR_STOP | typeof CHAT_ACTIONS.STOP_STREAMING | typeof CHAT_ACTIONS.CYCLE_TOKEN_COUNTER | typeof CHAT_ACTIONS.OPEN_CHARACTER_MAP | typeof CHAT_ACTIONS.OPEN_ATTACH_MODAL | typeof CHAT_ACTIONS.OPEN_CAMERA | typeof CHAT_ACTIONS.CANCEL_RAG_INGESTION | typeof CHAT_ACTIONS.TOGGLE_RECORDING | typeof CHAT_ACTIONS.CANCEL_RECORDING | typeof CHAT_ACTIONS.TOGGLE_CALL | typeof CHAT_ACTIONS.SAVE_CONFIGURATION | typeof CHAT_ACTIONS.SUGGESTION | typeof CHAT_ACTIONS.REMOVE_ATTACHED_FILE | typeof CHAT_ACTIONS.REMOVE_DRAFT_KNOWLEDGE_ATTACHMENT | typeof CHAT_ACTIONS.REMOVE_CONVERSATION_INPUT | typeof CHAT_ACTIONS.RETRY_CONVERSATION_REGENERATION | typeof CHAT_ACTIONS.COPY_CODE_BLOCK | typeof CHAT_ACTIONS.TOGGLE_TOOL_ACTIVITY_ITEM;

const applySuggestionToInput = (host: ChatComposerActionsHost, actionElement: HTMLElement): void => {
    const input = host.composer.requireInput();
    const value = host.presentation.actionData(actionElement, 'text');
    const text = isString(value) ? value : '';
    host.composer.setInput(input, text);
    input.focus();
    host.composer.updateInputState();
};

const resolveToolActivityToggleTaskId = (actionElement: HTMLElement): string => {
    const item = actionElement.closest('.inline-activity');
    const message = actionElement.closest('.chat-message');
    const callId = item instanceof HTMLElement ? (item.getAttribute('data-call-id')?.trim() ?? '') : '';
    const messageId = message instanceof HTMLElement ? (message.getAttribute('data-id')?.trim() ?? '') : '';
    if (callId && messageId) {
        return `chat:toggleToolActivity:${messageId}:${callId}`;
    }
    return 'chat:toggleToolActivity';
};

const openChatAttachmentModal = (host: ChatComposerActionsHost): void => {
    openChatAttachModal(host);
};

const openChatCameraModal = (host: ChatComposerActionsHost): void => {
    if (!host.attachments.cameraEnabled()) {
        throw new Error('Chat camera capture is not available');
    }
    openChatAttachModal(host, { initialTab: 'camera' });
};

const createChatComposerActionHandlers = (host: ChatComposerActionsHost): Record<ChatComposerActionId, ChatActionHandler> => {
    const mappedDirectActions = createMappedActionHandlers({
        [CHAT_ACTIONS.CYCLE_TOKEN_COUNTER]: () => host.composer.cycleTokenCounter(),
        [CHAT_ACTIONS.SAVE_CONFIGURATION]: () => host.configuration.save()
    });
    const collapsedDirectActions = createCollapsedActionHandlers(host, {
        [CHAT_ACTIONS.TOGGLE_RECORDING]: () => host.audio.toggleRecording(),
        [CHAT_ACTIONS.CANCEL_RECORDING]: () => host.audio.cancelRecording(),
        [CHAT_ACTIONS.TOGGLE_CALL]: () => host.composer.toggleCall()
    });
    return {
        [CHAT_ACTIONS.SEND_OR_STOP]: (actionElement) => executeComposerPrimaryAction(host, actionElement),
        [CHAT_ACTIONS.STOP_STREAMING]: (actionElement) => executeComposerPrimaryAction(host, actionElement, true),
        [CHAT_ACTIONS.OPEN_ATTACH_MODAL]: () => openChatAttachmentModal(host),
        [CHAT_ACTIONS.OPEN_CHARACTER_MAP]: () => host.composer.openCharacterMap(),
        [CHAT_ACTIONS.OPEN_CAMERA]: createPreventDefaultStoppedActionHandler((_actionElement: HTMLElement) => openChatCameraModal(host)),
        [CHAT_ACTIONS.CYCLE_TOKEN_COUNTER]: mappedDirectActions[CHAT_ACTIONS.CYCLE_TOKEN_COUNTER],
        [CHAT_ACTIONS.CANCEL_RAG_INGESTION]: () => host.execution.run('chat:cancelRagIngestion', () => host.rag.cancel()),
        [CHAT_ACTIONS.TOGGLE_RECORDING]: collapsedDirectActions[CHAT_ACTIONS.TOGGLE_RECORDING],
        [CHAT_ACTIONS.CANCEL_RECORDING]: collapsedDirectActions[CHAT_ACTIONS.CANCEL_RECORDING],
        [CHAT_ACTIONS.TOGGLE_CALL]: collapsedDirectActions[CHAT_ACTIONS.TOGGLE_CALL],
        [CHAT_ACTIONS.SAVE_CONFIGURATION]: mappedDirectActions[CHAT_ACTIONS.SAVE_CONFIGURATION],
        [CHAT_ACTIONS.SUGGESTION]: createCollapsedElementActionHandler(host, (actionElement: HTMLElement) => applySuggestionToInput(host, actionElement)),
        [CHAT_ACTIONS.REMOVE_ATTACHED_FILE]: (actionElement: HTMLElement) => {
            const fileId = host.presentation.actionData(actionElement, 'file-id');
            if (!fileId) {
                throw new Error('Chat attached-file remove action requires data-file-id');
            }
            host.execution.run('chat:removeAttachedFile', () => host.attachments.removeFile(fileId));
        },
        [CHAT_ACTIONS.REMOVE_DRAFT_KNOWLEDGE_ATTACHMENT]: (actionElement: HTMLElement) => {
            const knowledgeAttachmentId = host.presentation.actionData(actionElement, 'knowledge-attachment-id');
            if (!knowledgeAttachmentId) {
                throw new Error('Chat knowledge draft remove action requires data-knowledge-attachment-id');
            }
            host.execution.run('chat:removeDraftKnowledgeAttachment', () => host.attachments.removeKnowledge(knowledgeAttachmentId));
        },
        [CHAT_ACTIONS.REMOVE_CONVERSATION_INPUT]: (actionElement: HTMLElement) => {
            const inputId = host.presentation.actionData(actionElement, 'input-id');
            if (!inputId) {
                throw new Error('Chat conversation-input remove action requires data-input-id');
            }
            const conversationId = requireCurrentConversationId(host);
            runCollapsedUiTask(host, 'chat:removeConversationInput', async () => {
                await host.composer.cancelConversationInput(conversationId, inputId);
                host.composer.updateInputQueuePreview();
                host.composer.updateInputState();
            });
        },
        [CHAT_ACTIONS.RETRY_CONVERSATION_REGENERATION]: (actionElement: HTMLElement) => {
            const inputId = host.presentation.actionData(actionElement, 'input-id');
            if (!inputId) {
                throw new Error('Conversation regeneration retry requires data-input-id');
            }
            const conversationId = requireCurrentConversationId(host);
            runCollapsedUiTask(host, 'chat:retryConversationRegeneration', async () => {
                await host.composer.retryConversationRegeneration(conversationId, inputId);
                host.composer.updateInputQueuePreview();
                host.composer.updateInputState();
            });
        },
        [CHAT_ACTIONS.COPY_CODE_BLOCK]: createPreventDefaultStoppedActionHandler((actionElement: HTMLElement) => {
            host.execution.run('chat:copyCodeBlock', () => host.presentation.copyCodeBlock(actionElement));
        }),
        [CHAT_ACTIONS.TOGGLE_TOOL_ACTIVITY_ITEM]: createPreventDefaultStoppedActionHandler((actionElement: HTMLElement) => {
            host.execution.run(resolveToolActivityToggleTaskId(actionElement), () => host.presentation.toggleToolActivityItem(actionElement));
        })
    };
};

export { createChatComposerActionHandlers };
