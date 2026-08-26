/* SoAI - Chat page initializers effects [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationAttentionRenderedRequest, ConversationInteractionResolutionResponse, ConversationPendingInteractionResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import { securityApi } from '@core/security/public.ts';
import { buildAskUserPreviewMarkup, buildSecretPromptPreviewMarkup, buildToolApprovalPreviewMarkup, ChatElicitationPreview, ChatElicitationSession, CHAT_SELECTORS, focusAskUserPrompt, focusSecretPrompt, focusToolApprovalPrompt, parseAskUserPendingResponse, parseSecretPromptPendingResponse, parseToolApprovalPendingResponse, type ElicitationApi } from '@features/chat/public.ts';
import { initializeConversationManager, initializeMessageManager, initializeParameterManager } from '@pages/chat/controllers/chatpage/construction/initializers/adapters.ts';
import type { ChatControllerInitializationContext, Logger } from '@pages/chat/controllers/chatpage/construction/initializers/contracts.ts';
import { initializeAttachmentManager, initializeAudioManager, initializeConversationSettingsManager, initializeTtsManager, initializeUIManager } from '@pages/chat/controllers/chatpage/construction/initializers/service.ts';
import { initializeChatStreamingController, initializeChatTerminalIndicators, initializeComposerDraftManager, initializeConversationInputsManager, initializeStorageManager } from '@pages/chat/controllers/chatpage/construction/initializers/state.ts';

type McpElicitationPromptApi<TResolutionRequest> = {
    pending(conversationId: string): Promise<ConversationPendingInteractionResponse>;
    resolve(conversationId: string, taskId: string, request: TResolutionRequest): Promise<ConversationInteractionResolutionResponse>;
    acknowledgeRendered(conversationId: string, request: ConversationAttentionRenderedRequest): Promise<void>;
};

const createElicitationApi = <TResolutionRequest>(api: McpElicitationPromptApi<TResolutionRequest>): ElicitationApi<TResolutionRequest> => ({
    pending: async (conversationId) => api.pending(conversationId),
    resolve: async (conversationId, taskId, request) => api.resolve(conversationId, taskId, request),
    acknowledgeRendered: async (conversationId, request) => api.acknowledgeRendered(conversationId, request)
});

const initializeElicitationSession = (page: ChatControllerInitializationContext): void => {
    if (page.sessions.composer.hasElicitation()) return;
    const messages = page.runtime.conversationRuntime.requireMessages();
    const preview = new ChatElicitationPreview({
        optionalUI: (selector, context) => page.page.pageDom.optional(selector, context),
        queryUI: (selector, context) => page.page.pageDom.query(selector, context),
        updateHtml: (element, markup) => page.page.pageDom.updateHtml(element, markup),
        toggleClass: (element, className, add) => page.page.pageDom.toggleClass(element, className, add),
        updateAttribute: (element, attribute, value) => page.page.pageDom.updateAttribute(element, attribute, value)
    });
    const acknowledgeRendered = page.platform.api.webui.chat.interactions.attentionRendered;
    page.sessions.composer.initializeElicitation(
        new ChatElicitationSession({
            askUser: {
                type: 'askUser',
                interactionType: 'ask_user',
                previewSelector: CHAT_SELECTORS.ASK_USER_PREVIEW,
                api: createElicitationApi({ ...page.platform.api.webui.chat.interactions.askUser, acknowledgeRendered }),
                parse: parseAskUserPendingResponse,
                build: (prompt) => buildAskUserPreviewMarkup({ messageManager: securityApi }, prompt),
                focus: focusAskUserPrompt,
                syncFailureMessage: 'Failed to sync ask_user prompt',
                taskCreatedFailureMessage: 'Failed to sync ask_user prompt after task creation'
            },
            secretPrompt: {
                type: 'secretPrompt',
                interactionType: 'vault_secret_request',
                previewSelector: CHAT_SELECTORS.SECRET_PROMPT_PREVIEW,
                api: createElicitationApi({ ...page.platform.api.webui.chat.interactions.vaultSecretRequest, acknowledgeRendered }),
                parse: parseSecretPromptPendingResponse,
                build: (prompt) => buildSecretPromptPreviewMarkup({ messageManager: securityApi }, prompt),
                focus: focusSecretPrompt,
                syncFailureMessage: 'Failed to sync vault_secret_request prompt',
                taskCreatedFailureMessage: 'Failed to sync vault_secret_request prompt after task creation'
            },
            toolApproval: {
                type: 'toolApproval',
                interactionType: 'tool_approval',
                previewSelector: CHAT_SELECTORS.TOOL_APPROVAL_PREVIEW,
                api: createElicitationApi({ ...page.platform.api.webui.chat.interactions.toolApproval, acknowledgeRendered }),
                parse: parseToolApprovalPendingResponse,
                build: (prompt) => buildToolApprovalPreviewMarkup({ messageManager: securityApi }, prompt),
                focus: focusToolApprovalPrompt,
                syncFailureMessage: 'Failed to sync tool approval prompt',
                taskCreatedFailureMessage: 'Failed to sync tool approval prompt after task creation'
            },
            getCurrentConversationId: () => page.state.conversationState.currentConversationId,
            canAcknowledgePrompt: (conversationId) => page.state.runtimeServices.presence.isActivelyViewingConversation(conversationId),
            optionalUI: (selector) => page.page.pageDom.optional(selector),
            updatePreview: (type, markup) => preview.update(type, markup),
            postRender: (container) => messages.postRender(container),
            logWarning: (message, error) => errorHandler.warn('ChatElicitation', message, error),
            subscribeTaskCreated: (listener) => subscribeManagedWebSocketContract({ label: 'ChatElicitation', contract: WEBSOCKET_EVENT_CONTRACTS.task.created, handler: listener }),
            subscribeTaskComplete: (listener) => subscribeManagedWebSocketContract({ label: 'ChatElicitation', contract: WEBSOCKET_EVENT_CONTRACTS.task.complete, handler: listener })
        })
    );
};

const ensureChatPageManagersInitialized = (page: ChatControllerInitializationContext, logger: Logger): void => {
    initializeConversationManager(page);
    initializeMessageManager(page);
    initializeParameterManager(page);
    initializeStorageManager(page);
    initializeUIManager(page);
    initializeAttachmentManager(page, logger);
    initializeChatStreamingController(page);
    initializeChatTerminalIndicators(page);
    initializeConversationInputsManager(page);
    initializeElicitationSession(page);
    initializeConversationSettingsManager(page);
    initializeComposerDraftManager(page);
    initializeAudioManager(page);
    initializeTtsManager(page);
};

export { ensureChatPageManagersInitialized };
