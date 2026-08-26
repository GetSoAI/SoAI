/* SoAI - Chat page create message sending controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/createMessageSendingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { enhanceConversationExportInlineMedia, renderConversationExportMessages, resolveConversationExportSenderLabel, type ChatPageApi, type ConversationExportModelCategory, type ConversationExportModelDescriptor } from '@features/chat/public.ts';
import { ChatMessageSendingController } from '@pages/chat/controllers/chatmessagesendingcontroller/ChatMessageSendingController.ts';
import type { ChatMessageSendingPort } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';
import { ChatPageModelAvailabilityController } from '@pages/chat/controllers/chatpage/construction/ChatPageModelAvailabilityController.ts';
import { resolveVisionSupportForCurrentModel } from '@pages/chat/controllers/page/guards/modelVisionSupportController.ts';
import { isThinkingFeatureEnabled } from '@pages/chat/controllers/page/state.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatPageElementsHost } from '@pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ChatMessageConversationPort extends ChatConversationViewHost, ChatConversationStateHost, ChatComposerHost, ChatSettingsStateHost, ChatModelSessionHost, ChatPagePresentationHost {}

interface ChatMessageRuntimePort extends ChatComposerSurfaceRuntimeOwner, ChatConversationRuntimeOwner, ChatTurnRuntimeOwner, ChatPageElementsHost, ChatRuntimeServicesHost, PageUiOwnerHost {}

interface ChatMessagePlatformPort extends PageLifecycleOwnerHost, PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {}

interface ChatMessageSendingDependencies extends ChatMessageConversationPort, ChatMessageRuntimePort, ChatMessagePlatformPort {
    pageContext: { sanitizer: SanitizerApi };
    dom: { getDocument(): Document };
    api: ChatPageApi;
}

const resolveExportModelCategory = (type: string | undefined): ConversationExportModelCategory => {
    if (type === 'virtual' || type === 'cloud' || type === 'local') {
        return type;
    }
    return 'unknown';
};

const resolveExportModelDescriptor = (model: ModelData, modelId: string): ConversationExportModelDescriptor => {
    const displayName = isString(model.displayName) && model.displayName.trim() ? model.displayName.trim() : '';
    const name = displayName || (isString(model.name) && model.name.trim() ? model.name.trim() : modelId);
    return { name, category: resolveExportModelCategory(isString(model.type) ? model.type : undefined) };
};

const createChatMessageSendingController = (page: ChatMessageSendingDependencies, ensureManagersInitialized: (owner: ChatMessageSendingPort) => Promise<void>): ChatMessageSendingController => {
    const modelAvailability = new ChatPageModelAvailabilityController({
        getModelIndex: () => page.conversationState.modelIndex,
        getModels: () => page.conversationState.models,
        getModelStreamHasPayload: () => page.conversationState.modelStreamHasPayload
    });
    return new ChatMessageSendingController({
        platform: {
            pageDom: page.pageDom,
            pageResources: page.pageResources,
            feedback: page.feedback,
            runWithBoundary: (name, functionValue) => page.pageLifecycle.run(name, functionValue),
            handleError: (error, title, options) => page.feedback.handle(error, title, options),
            getDocument: () => page.dom.getDocument(),
            ensureManagersInitialized,
            ensureConversationForSend: async () => {
                const existingConversation = page.conversationView.current();
                if (existingConversation) {
                    return { conversationId: existingConversation.id, created: false };
                }
                const createdConversation = await page.conversationView.requireActions().createConversation({ transferMode: 'adopt-current' });
                return createdConversation ? { conversationId: createdConversation.id, created: true } : null;
            },
            getRuntimeAbortSignal: () => page.pageLifecycle.signal(),
            subscribeKnowledgeAttachmentChanged: (listener) =>
                subscribeManagedWebSocketContract({
                    label: 'ChatKnowledgeAttachments',
                    contract: WEBSOCKET_EVENT_CONTRACTS.attachment.knowledgeChanged,
                    handler: listener
                })
        },
        composer: {
            getChatInput: () => page.elements.getChatInputElement(),
            queryDocumentUI: (selector) => page.elements.queryDocumentUI(selector),
            setUIValue: (target, value, options) => page.pageElements.setValue(target, value, options),
            resizeChatInput: (element) => page.composer.resizeInput(element),
            noteChatInputDraftChanged: (value) => page.composer.noteDraftChanged(value),
            updateInputState: () => page.composerSurface.requireUi().updateInputState()
        },
        presentation: {
            updateEmptyStateInputHint: () => page.composer.updateEmptyStateInputHint(),
            refreshConversationsUI: () => page.conversationView.refresh(),
            invalidateChatMarkup: (scope) => page.conversationView.invalidate(scope),
            renderCurrentConversation: () => page.conversationView.renderCurrent(),
            flushDOMUpdates: () => page.pageDom.flush(),
            renderAttachedFilesPreview: () => page.composerSurface.requireUi().updateAttachmentsPreview(),
            hideAttachedFilesPreview: () => page.composerSurface.requireUi().clearAttachedFiles(),
            updateExportButtonVisibility: () => page.presentation.updateExportButtonVisibility(),
            shouldAutoScrollAfterContentUpdate: () => page.composerSurface.requireUi().shouldAutoScrollAfterContentUpdate(),
            forceTimelineScrollToBottom: () => page.composerSurface.requireUi().forceScrollToBottom()
        },
        conversation: {
            getCurrentConversation: () => page.conversationView.current(),
            getConversationById: (conversationId) => {
                const conversation = page.conversationState.conversations.get(conversationId);
                return conversation === undefined ? null : conversation;
            },
            isConversationExecuting: (conversationId) => page.conversationView.isExecuting(conversationId),
            commitPendingDeletesForConversation: async (conversation) => {
                await page.conversationRuntime.requireMessages().commitPendingDeletesForConversation(conversation);
            },
            conversations: page.conversationState.conversations,
            resolveAgentModeForConversation: (conversationId) => page.turnRuntime.requireAgent().resolveModeForConversation(conversationId),
            waitForPendingAgentModeUpdate: () => page.turnRuntime.requireAgent().waitForPendingModeUpdate()
        },
        model: {
            getCurrentModel: () => {
                const currentModel = page.conversationState.currentModel;
                return isString(currentModel) && currentModel.trim() ? currentModel : null;
            },
            resolveModelDescriptor: (modelId) => {
                const model = page.conversationState.modelIndex.get(modelId);
                return model === undefined ? null : resolveExportModelDescriptor(model, modelId);
            },
            isVisionSupportedForCurrentModel: () => resolveVisionSupportForCurrentModel(page),
            getModelStreamHasPayload: modelAvailability.getModelStreamHasPayload,
            isModelAvailable: modelAvailability.isModelAvailable,
            getParameters: () => page.settings.parameters
        },
        services: {
            getSoaiLinkResolutionManager: () => page.composerSurface.requireSoaiLinkResolution(),
            getAttachmentManager: () => page.composerSurface.requireAttachments(),
            getStorageManager: () => page.conversationRuntime.requireStorage(),
            getChatStreamingController: () => page.turnRuntime.requireStreaming(),
            getConversationManager: () => page.conversationRuntime.requireConversation(),
            getConversationInputsManager: () => page.turnRuntime.requireConversationInputs(),
            getChatApi: () => page.api,
            getChatPreferences: () => page.settings.storage.getChatPreferences(),
            renderConversationExportMessages: (conversation) =>
                renderConversationExportMessages({
                    conversation,
                    sanitizer: page.pageContext.sanitizer,
                    chatToolIconService: page.runtimeServices.toolIcons,
                    getCachedIcon: (name, options) => page.presentation.cachedIcon(name, options),
                    getMessageSenderLabel: (source, defaultRole) =>
                        resolveConversationExportSenderLabel({
                            message: source,
                            role: defaultRole,
                            parameters: page.settings.parameters,
                            conversation,
                            currentModel: page.conversationState.currentModel,
                            getModelDisplayName: (modelId) => page.modelSession.displayName(modelId)
                        }),
                    isThinkingFeatureEnabled,
                    isRichTextEnabled: () => page.settings.richTextEnabled(),
                    isCodeRecognitionEnabled: () => page.settings.storage.getCodeRecognitionEnabled(),
                    isInlineMultimediaPreviewsEnabled: () => page.settings.inlineMultimediaPreviewsEnabled(),
                    isShowActivitiesEnabled: () => page.settings.showActivitiesEnabled(),
                    getAssistantAvatarUrl: () => page.settings.storage.getAssistantAvatar(),
                    getUserAvatarUrl: () => page.settings.storage.getUserAvatar(),
                    handleError: (error, context, options) => {
                        if (options?.notify === undefined) {
                            page.feedback.handle(error, context);
                            return;
                        }
                        page.feedback.handle(error, context, { notify: options.notify });
                    }
                }),
            enhanceConversationExportInlineMedia: (container, conversationId) =>
                enhanceConversationExportInlineMedia({
                    apiClient: { request: (method, endpoint, body, options) => page.api.request(method, endpoint, body, options) },
                    container,
                    conversationId
                })
        }
    });
};

export { createChatMessageSendingController };
export type { ChatMessageSendingDependencies };
