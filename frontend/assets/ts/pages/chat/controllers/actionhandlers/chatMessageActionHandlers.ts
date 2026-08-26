/* SoAI - Chat page message action handlers [frontend/assets/ts/pages/chat/controllers/actionhandlers/chatMessageActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireNonNegativeIntegerAttribute } from '@core/dom/attributes.ts';
import { parseRequiredJsonObjectText } from '@core/serialization/json.ts';
import { CHAT_ACTIONS, ChatSoaiFileContentPreview, ChatSoaiPathContentPreview, isSoaiFilePreviewType, normalizeSoaiPathStoragePart, openKnowledgeAttachmentFirstPreview, type ChatActionId } from '@features/chat/public.ts';
import { handleOpenMultimediaPreviewAction, type ChatMultimediaPreviewActionHost } from '@pages/chat/controllers/actionhandlers/chatMultimediaPreviewActionController.ts';
import type { SoaiPathOperationRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import type { ChatConfigurationActionPort, ChatConversationActionPort, ChatExecutionActionPort, ChatPresentationActionPort, ChatRagActionPort, ChatSharedActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

type ChatActionHandler = (actionElement: HTMLElement, event: Event) => void;

type ChatMessageActionId =
    | typeof CHAT_ACTIONS.SELECT_CONVERSATION_COLOR
    | typeof CHAT_ACTIONS.TOGGLE_CONVERSATION_FAVORITE
    | typeof CHAT_ACTIONS.ARCHIVE_CONVERSATION
    | typeof CHAT_ACTIONS.COPY_TIMESTAMP
    | typeof CHAT_ACTIONS.DELETE
    | typeof CHAT_ACTIONS.DELETE_NOW
    | typeof CHAT_ACTIONS.DELETE_UNDO
    | typeof CHAT_ACTIONS.COPY
    | typeof CHAT_ACTIONS.SPEAK
    | typeof CHAT_ACTIONS.RESEND
    | typeof CHAT_ACTIONS.EDIT
    | typeof CHAT_ACTIONS.EDIT_SAVE
    | typeof CHAT_ACTIONS.EDIT_CANCEL
    | typeof CHAT_ACTIONS.INFO
    | typeof CHAT_ACTIONS.REGENERATE
    | typeof CHAT_ACTIONS.REMOVE_COMPACTION_BOUNDARY
    | typeof CHAT_ACTIONS.STOP_SHELL
    | typeof CHAT_ACTIONS.OPEN_TOOL_CALL_OUTPUT
    | typeof CHAT_ACTIONS.OPEN_MULTIMEDIA_PREVIEW
    | typeof CHAT_ACTIONS.COPY_INLINE_MEDIA_REFERENCE
    | typeof CHAT_ACTIONS.OPEN_INLINE_LOCAL_FOLDER
    | typeof CHAT_ACTIONS.OPEN_ATTACHMENT_OVERFLOW
    | typeof CHAT_ACTIONS.OPEN_KNOWLEDGE_ATTACHMENT_PREVIEW
    | typeof CHAT_ACTIONS.OPEN_SOAI_FILE_PREVIEW
    | typeof CHAT_ACTIONS.OPEN_SOAI_PATH_PREVIEW
    | typeof CHAT_ACTIONS.REVEAL_RUNNING_ACTIVITY
    | typeof CHAT_ACTIONS.TOGGLE_LOADING_ACTIVITY_ITEM;

type DispatchOnlyMessageActionId = typeof CHAT_ACTIONS.COPY_TIMESTAMP | typeof CHAT_ACTIONS.DELETE | typeof CHAT_ACTIONS.DELETE_NOW | typeof CHAT_ACTIONS.DELETE_UNDO | typeof CHAT_ACTIONS.COPY | typeof CHAT_ACTIONS.SPEAK | typeof CHAT_ACTIONS.RESEND | typeof CHAT_ACTIONS.EDIT | typeof CHAT_ACTIONS.EDIT_SAVE | typeof CHAT_ACTIONS.EDIT_CANCEL | typeof CHAT_ACTIONS.INFO | typeof CHAT_ACTIONS.REGENERATE | typeof CHAT_ACTIONS.REMOVE_COMPACTION_BOUNDARY | typeof CHAT_ACTIONS.STOP_SHELL | typeof CHAT_ACTIONS.OPEN_ATTACHMENT_OVERFLOW | typeof CHAT_ACTIONS.REVEAL_RUNNING_ACTIVITY | typeof CHAT_ACTIONS.TOGGLE_LOADING_ACTIVITY_ITEM;

type ConversationActionsController = {
    toggleConversationFavoriteById(conversationId: string): void;
    archiveConversationById(conversationId: string): void;
    updateConversationColorById(conversationId: string, color: string | null): void;
};

interface ChatMessageActionHandlersHost {
    configuration: ChatConfigurationActionPort;
    conversation: ChatConversationActionPort;
    execution: ChatExecutionActionPort;
    presentation: ChatPresentationActionPort;
    rag: ChatRagActionPort;
    shared: ChatSharedActionPort;
}

const requireAssistantComparisonIdentityFromAction = (actionElement: HTMLElement): { assistantTurnTimestamp: number; modelVariantIndex: number } => {
    return {
        assistantTurnTimestamp: requireNonNegativeIntegerAttribute(actionElement, 'data-assistant-turn-ts', 'Chat tool output action'),
        modelVariantIndex: requireNonNegativeIntegerAttribute(actionElement, 'data-model-variant-index', 'Chat tool output action')
    };
};

const requireActiveColorPickerConversationId = (host: ChatMessageActionHandlersHost): string => {
    const conversationId = host.presentation.activeColorPickerConversationId();
    if (!conversationId) {
        throw new Error('ChatPage requires an active conversation for color selection');
    }
    return conversationId;
};

const applyColorPickerConversationControllerAction = (host: ChatMessageActionHandlersHost, action: (controller: ConversationActionsController, conversationId: string) => void): void => {
    const conversationId = requireActiveColorPickerConversationId(host);
    const controller = host.conversation.actions;
    action(controller, conversationId);
    host.presentation.hideColorPicker();
};

const createDispatchMessageActionHandler = (host: ChatMessageActionHandlersHost, action: ChatActionId): ChatActionHandler => {
    return (actionElement: HTMLElement, event: Event): void => {
        host.presentation.dispatchMessageAction(actionElement, action, event);
    };
};

const createDispatchMessageActionHandlers = (host: ChatMessageActionHandlersHost): Record<DispatchOnlyMessageActionId, ChatActionHandler> => {
    return {
        [CHAT_ACTIONS.COPY_TIMESTAMP]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.COPY_TIMESTAMP),
        [CHAT_ACTIONS.DELETE]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.DELETE),
        [CHAT_ACTIONS.DELETE_NOW]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.DELETE_NOW),
        [CHAT_ACTIONS.DELETE_UNDO]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.DELETE_UNDO),
        [CHAT_ACTIONS.COPY]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.COPY),
        [CHAT_ACTIONS.SPEAK]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.SPEAK),
        [CHAT_ACTIONS.RESEND]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.RESEND),
        [CHAT_ACTIONS.EDIT]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.EDIT),
        [CHAT_ACTIONS.EDIT_SAVE]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.EDIT_SAVE),
        [CHAT_ACTIONS.EDIT_CANCEL]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.EDIT_CANCEL),
        [CHAT_ACTIONS.INFO]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.INFO),
        [CHAT_ACTIONS.REGENERATE]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.REGENERATE),
        [CHAT_ACTIONS.REMOVE_COMPACTION_BOUNDARY]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.REMOVE_COMPACTION_BOUNDARY),
        [CHAT_ACTIONS.STOP_SHELL]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.STOP_SHELL),
        [CHAT_ACTIONS.OPEN_ATTACHMENT_OVERFLOW]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.OPEN_ATTACHMENT_OVERFLOW),
        [CHAT_ACTIONS.REVEAL_RUNNING_ACTIVITY]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.REVEAL_RUNNING_ACTIVITY),
        [CHAT_ACTIONS.TOGGLE_LOADING_ACTIVITY_ITEM]: createDispatchMessageActionHandler(host, CHAT_ACTIONS.TOGGLE_LOADING_ACTIVITY_ITEM)
    };
};

const createColorPickerConversationActionHandler = (host: ChatMessageActionHandlersHost, action: (controller: ConversationActionsController, conversationId: string, actionElement: HTMLElement) => void): ChatActionHandler => {
    return (actionElement: HTMLElement): void => {
        applyColorPickerConversationControllerAction(host, (controller, conversationId) => action(controller, conversationId, actionElement));
    };
};

const createChatMultimediaPreviewActionHost = (host: ChatMessageActionHandlersHost): ChatMultimediaPreviewActionHost => {
    return {
        hasClipboardSupport: () => host.presentation.hasClipboardSupport(),
        copyToClipboard: (text, options) => host.presentation.copyToClipboard(text, options),
        showNotification: (message, type) => host.shared.feedback.show(message, type),
        requestConversationSoaiPathToken: (conversationId: string, payload: SoaiPathOperationRequest) => host.shared.api.webui.chat.soaiPaths.token(conversationId, payload)
    };
};

const fetchSoaiFilePreviewText = async (host: ChatMessageActionHandlersHost, url: string, signal: AbortSignal): Promise<string> => {
    const response = await host.shared.api.request('GET', url, null, { rawResponse: true, signal });
    if (!(typeof Response === 'function' && response instanceof Response)) {
        throw new Error('Chat SoAI file text preview did not return a Response');
    }
    return response.text();
};

const openKnowledgePreview = (host: ChatMessageActionHandlersHost, actionElement: HTMLElement): void => {
    const conversationId = host.conversation.currentId();
    if (!conversationId) {
        throw new Error('Chat knowledge preview requires an active conversation');
    }
    const knowledgeAttachmentId = host.presentation.actionData(actionElement, 'knowledgeAttachmentId');
    if (!knowledgeAttachmentId) {
        throw new Error('Chat knowledge preview requires a knowledge attachment id');
    }
    const fallbackTitle = host.presentation.actionData(actionElement, 'knowledgeTitle') ?? i18n.t('chat.ingestion.title');
    host.execution.run('chat:openKnowledgeAttachmentPreview', () =>
        openKnowledgeAttachmentFirstPreview({
            knowledgeAttachmentsApi: host.shared.api.webui.chat.attachments.knowledge,
            targetConversationId: conversationId,
            sourceConversationId: conversationId,
            knowledgeAttachmentId,
            fallbackTitle,
            hasClipboardSupport: () => host.presentation.hasClipboardSupport(),
            copyToClipboard: (text, options) => host.presentation.copyToClipboard(text, options),
            showNotification: (message, type) => host.shared.feedback.show(message, type),
            onKnowledgeAttachmentChanged: (summary) => host.rag.handleKnowledgeChanged(summary),
            shouldOpen: () => host.conversation.currentId() === conversationId
        })
    );
};

const openSoaiFilePreview = (host: ChatMessageActionHandlersHost, preview: ChatSoaiFileContentPreview, actionElement: HTMLElement): void => {
    const previewType = host.presentation.actionData(actionElement, 'soaiFilePreviewType');
    const previewUrl = host.presentation.actionData(actionElement, 'soaiFilePreviewUrl');
    const downloadUrl = host.presentation.actionData(actionElement, 'soaiFileDownloadUrl');
    const title = host.presentation.actionData(actionElement, 'soaiFileTitle');
    const conversationId = host.presentation.actionData(actionElement, 'soaiFileConversationId');
    if (!previewType || !isSoaiFilePreviewType(previewType) || !previewUrl || !downloadUrl || !title || !conversationId) {
        throw new Error('Chat SoAI file preview requires a complete preview dataset');
    }
    const contentLength = requireNonNegativeIntegerAttribute(actionElement, 'data-soai-file-content-length', 'Chat SoAI file preview');
    preview.open({
        title,
        previewType,
        previewUrl,
        downloadUrl,
        contentType: host.presentation.actionData(actionElement, 'soaiFileContentType'),
        contentLength,
        isCurrent: () => host.conversation.currentId() === conversationId
    });
};

const openSoaiPathPreview = (host: ChatMessageActionHandlersHost, preview: ChatSoaiPathContentPreview, actionElement: HTMLElement): void => {
    const conversationId = host.conversation.currentId();
    if (!conversationId) {
        throw new Error('Chat SoAI path preview requires an active conversation');
    }
    const contentPartText = host.presentation.actionData(actionElement, 'soaiPathContentPart');
    if (!contentPartText) {
        throw new Error('Chat SoAI path preview requires a content part');
    }
    const title = host.presentation.actionData(actionElement, 'soaiPathTitle') ?? i18n.t('chat.attachments.badge.soaiLink');
    const contentPart = normalizeSoaiPathStoragePart(parseRequiredJsonObjectText(contentPartText, 'Chat SoAI path preview content part must be valid JSON'));
    if (contentPart === null) {
        throw new Error('Chat SoAI path preview content part must be canonical.');
    }
    preview.open({
        conversationId,
        title,
        contentPart,
        isCurrent: () => host.conversation.currentId() === conversationId
    });
};

const createChatMessageActionHandlers = (host: ChatMessageActionHandlersHost): Record<ChatMessageActionId, ChatActionHandler> => {
    const dispatchHandlers = createDispatchMessageActionHandlers(host);
    const multimediaPreviewHost = createChatMultimediaPreviewActionHost(host);
    const soaiFilePreview = new ChatSoaiFileContentPreview({
        runWithBoundary: (name, functionValue) => host.execution.boundary(name, functionValue),
        fetchText: (url, signal) => fetchSoaiFilePreviewText(host, url, signal),
        hasClipboardSupport: () => host.presentation.hasClipboardSupport(),
        copyToClipboard: (text, options) => host.presentation.copyToClipboard(text, options),
        showNotification: (message, type) => host.shared.feedback.show(message, type)
    });
    const soaiPathPreview = new ChatSoaiPathContentPreview({
        soaiPathsApi: host.shared.api.webui.chat.soaiPaths,
        runWithBoundary: (name, functionValue) => host.execution.boundary(name, functionValue),
        hasClipboardSupport: () => host.presentation.hasClipboardSupport(),
        copyToClipboard: (text, options) => host.presentation.copyToClipboard(text, options),
        showNotification: (message, type) => host.shared.feedback.show(message, type)
    });
    return {
        [CHAT_ACTIONS.SELECT_CONVERSATION_COLOR]: createColorPickerConversationActionHandler(host, (controller, conversationId, actionElement) => {
            const colorValue = host.presentation.actionData(actionElement, 'color');
            const color = isString(colorValue) && colorValue ? colorValue : null;
            controller.updateConversationColorById(conversationId, color);
        }),
        [CHAT_ACTIONS.TOGGLE_CONVERSATION_FAVORITE]: createColorPickerConversationActionHandler(host, (controller, conversationId) => {
            controller.toggleConversationFavoriteById(conversationId);
        }),
        [CHAT_ACTIONS.ARCHIVE_CONVERSATION]: createColorPickerConversationActionHandler(host, (controller, conversationId) => {
            controller.archiveConversationById(conversationId);
        }),
        [CHAT_ACTIONS.OPEN_TOOL_CALL_OUTPUT]: (actionElement: HTMLElement, event: Event): void => {
            const conversationId = host.conversation.currentId();
            if (!conversationId) {
                throw new Error('Chat tool output requires an active conversation');
            }
            const callIdValue = host.presentation.actionData(actionElement, 'callId');
            if (!isString(callIdValue) || !callIdValue.trim()) {
                throw new Error('Chat tool output action requires a tool call id');
            }
            const callId = callIdValue.trim();
            const comparisonIdentity = requireAssistantComparisonIdentityFromAction(actionElement);
            host.execution.run(`chat:openToolCallOutput:${callId}:${String(event.timeStamp)}`, () =>
                host.configuration.openToolOutput({
                    conversationId,
                    callId,
                    assistantTurnTimestamp: comparisonIdentity.assistantTurnTimestamp,
                    modelVariantIndex: comparisonIdentity.modelVariantIndex
                })
            );
        },
        [CHAT_ACTIONS.COPY_INLINE_MEDIA_REFERENCE]: (actionElement: HTMLElement, event: Event): void => {
            host.execution.run(`chat:copyInlineMediaReference:${String(event.timeStamp)}`, () => host.presentation.copyInlineMediaReference(actionElement));
        },
        [CHAT_ACTIONS.OPEN_INLINE_LOCAL_FOLDER]: (actionElement: HTMLElement, event: Event): void => {
            host.execution.run(`chat:openInlineLocalFolder:${String(event.timeStamp)}`, () => host.presentation.openInlineMediaLocalFolder(actionElement));
        },
        [CHAT_ACTIONS.OPEN_MULTIMEDIA_PREVIEW]: (actionElement: HTMLElement): void => {
            handleOpenMultimediaPreviewAction(multimediaPreviewHost, actionElement);
        },
        [CHAT_ACTIONS.OPEN_KNOWLEDGE_ATTACHMENT_PREVIEW]: (actionElement: HTMLElement): void => openKnowledgePreview(host, actionElement),
        [CHAT_ACTIONS.OPEN_SOAI_FILE_PREVIEW]: (actionElement: HTMLElement): void => openSoaiFilePreview(host, soaiFilePreview, actionElement),
        [CHAT_ACTIONS.OPEN_SOAI_PATH_PREVIEW]: (actionElement: HTMLElement): void => openSoaiPathPreview(host, soaiPathPreview, actionElement),
        ...dispatchHandlers
    };
};

export { createChatMessageActionHandlers };
