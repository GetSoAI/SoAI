/* SoAI - Chat page state [frontend/assets/ts/pages/chat/controllers/page/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isString } from '@core/typeGuards.ts';
import { canInteractivelyAdjustConversationTools, CHAT_ACTIONS, isChatConversationSettingsWritable, normalizeConversationId, normalizeMessageDomId, requireConversationId, resolveChatRequestErrorNotificationMessage, resolveConversationDisplayTitleFromConversation, setRunningActivityRevealPending, type ChatActionId, type ChatMessageManager, type ChatParameters, type Conversation, type ConversationWorkspacePathConfig, type McpConfig } from '@features/chat/public.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ChatRequestFailureHost extends ChatConversationStateHost, PageFeedbackOwnerHost {}

interface ChatConversationModelSettingsHost {
    conversations: Map<string, Conversation>;
    saveState(force?: boolean): void;
}

interface ChatMessageActionHost {
    dom: {
        getData(element: Element | null, key: string): string | null;
    };
    runUiTask(operationId: string, task: () => Promise<void>): void;
    messageManager: ChatMessageManager;
}

const getCurrentConversation = (host: ChatConversationStateHost): Conversation | null => {
    const conversationId = host.conversationState.currentConversationId;
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return null;
    }
    const conversation = host.conversationState.conversations.get(normalizedConversationId);
    return conversation ? conversation : null;
};

const reportRequestFailure = (host: ChatRequestFailureHost, error: Error): void => {
    const currentConversation = getCurrentConversation(host);
    const title = currentConversation ? resolveConversationDisplayTitleFromConversation(currentConversation, '') : null;
    const message = resolveChatRequestErrorNotificationMessage({ error, title });
    errorHandler.error('ChatPage', message, error);
    host.feedback.show(message, 'error', 6000);
};

const updateConversationModelSection = (host: ChatConversationModelSettingsHost, conversationId: string, updater: (nextSettings: NonNullable<Conversation['modelSettings']>) => void): void => {
    const conversation = host.conversations.get(conversationId);
    if (!conversation) {
        return;
    }
    const currentSettings = conversation.modelSettings;
    const nextSettings: NonNullable<Conversation['modelSettings']> = currentSettings ? { ...currentSettings } : { model: null };
    updater(nextSettings);
    conversation.modelSettings = nextSettings;
    host.saveState(true);
};

const applyMcpConfigToConversationModelSettings = (host: ChatConversationModelSettingsHost, conversationId: string, config: McpConfig): boolean => {
    const conversation = host.conversations.get(conversationId);
    if (!conversation || !conversation.modelSettings || !canInteractivelyAdjustConversationTools(conversation)) {
        return false;
    }
    updateConversationModelSection(host, conversationId, (nextSettings) => {
        nextSettings.mcp = {
            defaultTools: [...config.defaultTools],
            planTools: [...config.planTools],
            executeTools: [...config.executeTools],
            serverConfigs: { ...config.serverConfigs },
            toolsEnabled: config.toolsEnabled,
            toolApprovalRequired: config.toolApprovalRequired
        };
    });
    return true;
};

const updateConversationWorkspacePathConfig = (host: ChatConversationModelSettingsHost, conversationId: string, config: ConversationWorkspacePathConfig): boolean => {
    const writableConversation = host.conversations.get(conversationId);
    if (!isChatConversationSettingsWritable(writableConversation ?? null)) {
        return false;
    }
    updateConversationModelSection(host, conversationId, (nextSettings) => {
        const overrideValue = typeof config.workspacePath === 'string' ? config.workspacePath.trim() : '';
        if (overrideValue) {
            nextSettings.workspacePath = overrideValue;
        } else {
            delete nextSettings.workspacePath;
        }
    });
    const conversation = host.conversations.get(conversationId);
    if (!conversation) {
        return false;
    }
    const effectiveWorkspacePath = typeof config.effectiveWorkspacePath === 'string' ? config.effectiveWorkspacePath.trim() : '';
    if (effectiveWorkspacePath) {
        conversation.effectiveWorkspacePath = effectiveWorkspacePath;
    } else {
        delete conversation.effectiveWorkspacePath;
    }
    const effectiveRootFingerprint = typeof config.effectiveRootFingerprint === 'string' ? config.effectiveRootFingerprint.trim() : '';
    if (effectiveRootFingerprint) {
        conversation.effectiveWorkspaceRootFingerprint = effectiveRootFingerprint;
    } else {
        delete conversation.effectiveWorkspaceRootFingerprint;
    }
    return true;
};

const dispatchMessageAction = (host: ChatMessageActionHost, actionElement: HTMLElement, action: ChatActionId, event: Event): void => {
    const messageRoot = actionElement.closest('.chat-message');
    if (!(messageRoot instanceof Element)) {
        throw new Error('Chat message action must be within a chat message element');
    }
    const messageId = host.dom.getData(messageRoot, 'id');
    if (!isString(messageId)) {
        throw new Error('Chat message action requires a message id');
    }
    const normalizedMessageId = normalizeMessageDomId(messageId);
    if (!normalizedMessageId) {
        throw new Error('Chat message action requires a message id');
    }
    const timestamp = host.dom.getData(actionElement, 'timestamp');
    const knowledgeAttachmentId = host.dom.getData(actionElement, 'knowledgeAttachmentId');
    const callId = host.dom.getData(actionElement, 'callId');
    const assistantTurnTs = host.dom.getData(actionElement, 'assistantTurnTs');
    const modelVariantIndex = host.dom.getData(actionElement, 'modelVariantIndex');
    const actionData = {
        timestamp,
        knowledgeAttachmentId,
        callId,
        assistantTurnTs,
        modelVariantIndex,
        actionElement
    };

    if (action === 'copy-timestamp') {
        host.runUiTask(`chat:messageAction:copyTimestamp:${normalizedMessageId}:${String(event.timeStamp)}`, () => host.messageManager.handleMessageAction(normalizedMessageId, action, actionData));
        return;
    }
    if (action === CHAT_ACTIONS.TOGGLE_LOADING_ACTIVITY_ITEM) {
        host.runUiTask(`chat:messageAction:toggleLoadingActivity:${normalizedMessageId}`, () => host.messageManager.handleMessageAction(normalizedMessageId, action, actionData));
        return;
    }

    let operationId = 'chat:messageAction';
    if (action === CHAT_ACTIONS.REGENERATE) {
        operationId = `chat:messageAction:regenerate:${normalizedMessageId}:${String(event.timeStamp)}`;
    } else if (action === CHAT_ACTIONS.REMOVE_COMPACTION_BOUNDARY) {
        operationId = `chat:messageAction:removeCompactionBoundary:${normalizedMessageId}:${String(event.timeStamp)}`;
    } else if (action === CHAT_ACTIONS.STOP_SHELL) {
        operationId = `chat:messageAction:stopShell:${normalizedMessageId}:${callId ?? ''}:${String(event.timeStamp)}`;
    } else if (action === CHAT_ACTIONS.REVEAL_RUNNING_ACTIVITY) {
        operationId = `chat:messageAction:revealRunningActivity:${normalizedMessageId}:${String(event.timeStamp)}`;
        setRunningActivityRevealPending(actionElement, true);
    } else if (action === 'speak') {
        operationId = `chat:messageAction:speak:${normalizedMessageId}:${String(event.timeStamp)}`;
    }
    host.runUiTask(operationId, () => host.messageManager.handleMessageAction(normalizedMessageId, action, actionData));
    if (action === 'edit-save' || action === 'edit-cancel') {
        event.stopImmediatePropagation();
    }
};

const requireConversationIdFromElement = (dom: { getData(element: Element | null, key: string): string | null }, actionElement: HTMLElement, ancestorSelector: string | null): string => {
    const conversationElement = ancestorSelector ? actionElement.closest(ancestorSelector) : actionElement;
    if (!(conversationElement instanceof Element)) {
        throw new Error('Chat conversation action must target a conversation element');
    }
    const conversationId = dom.getData(conversationElement, 'id');
    return requireConversationId(conversationId, 'Chat conversation action');
};

const isThinkingFeatureEnabled = (): boolean => true;

const isRichTextEnabled = (parameters: ChatParameters): boolean => parameters.richTextEnabled !== false;

const isInlineMultimediaPreviewsEnabled = (parameters: ChatParameters): boolean => parameters.inlineMultimediaPreviewsEnabled !== false;

const isShowActivitiesEnabled = (parameters: ChatParameters): boolean => parameters.showActivities !== false;

export { applyMcpConfigToConversationModelSettings, dispatchMessageAction, getCurrentConversation, isInlineMultimediaPreviewsEnabled, isRichTextEnabled, isShowActivitiesEnabled, isThinkingFeatureEnabled, reportRequestFailure, requireConversationIdFromElement, updateConversationWorkspacePathConfig };
