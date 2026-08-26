/* SoAI - Chat page token counter [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/tokenCounter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeChatMobileAuxiliaryAction } from '@core/chat/parameters/mobileAuxiliaryAction.ts';
import { isPageTerminating } from '@core/lifecycle/pageTermination.ts';
import { sendWebSocketMessage } from '@core/websocketclient/service.ts';
import { serializeStorageContentPart } from '@features/chat/public.ts';
import { ChatTokenCounterController } from '@pages/chat/widgets/tokencounter/ChatTokenCounterController.ts';
import { requireChatTokenCounterLabel } from '@pages/chat/widgets/tokencounter/dom.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatConversationState } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatConversationViewController } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatSettingsState } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatPageElementsManager } from '@pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts';
import type { ChatUiTaskScopeManager } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ChatTokenCounterDependencies extends ChatComposerSurfaceRuntimeOwner, ChatConversationRuntimeOwner, ChatTurnRuntimeOwner {
    conversationState: ChatConversationState;
    conversationView: ChatConversationViewController;
    settings: ChatSettingsState;
    elements: ChatPageElementsManager;
    taskScope: ChatUiTaskScopeManager;
    services: PageServices;
    pageDom: PageDom;
    feedback: PageFeedback;
}

const createChatTokenCounter = (page: ChatTokenCounterDependencies): ChatTokenCounterController => {
    const controller = new ChatTokenCounterController({
        host: {
            pageDom: page.pageDom,
            feedback: page.feedback,
            getCurrentConversationId: () => page.conversationState.currentConversationId,
            getCurrentConversation: () => page.conversationView.current(),
            getCurrentModel: () => page.conversationState.currentModel,
            hasSelectableModels: () => page.conversationState.modelAvailability?.hasSelectableModels() === true,
            isModelAvailable: (modelId) => page.conversationState.modelAvailability?.isModelAvailable(modelId) === true,
            isConversationPersisted: (conversationId) => page.conversationRuntime.optionalConversation()?.isConversationPersisted(conversationId) === true,
            getRequestParameters: () => page.settings.requestParameters(),
            getDraftText: () => page.elements.getChatInputElement()?.value ?? '',
            getDraftAttachmentContent: () => {
                const attachmentManager = page.composerSurface.requireAttachments();
                return attachmentManager
                    .buildContentFragmentsFromAttachments(attachmentManager.getAttachments())
                    .map(serializeStorageContentPart)
                    .filter((part) => part !== null);
            },
            subscribeDraftAttachmentChanges: (listener) => page.composerSurface.requireAttachments().subscribeDraftChanges(listener),
            isTokenCounterInputActionEnabled: () => page.settings.parameters.inputActionTokenCounterEnabled === true || normalizeChatMobileAuxiliaryAction(page.settings.parameters.inputActionMobileAuxiliaryAction) === 'token_counter',
            isPageTerminating: () => isPageTerminating(),
            requireTokenCounterButtons: () => page.elements.requireTokenCounterButtons(),
            requireTokenCounterLabel: (button) => requireChatTokenCounterLabel(button),
            runUiTask: (operationId, task) => page.taskScope.run(operationId, task),
            createDebouncedHandler: (functionValue, delay) => page.services.createDebouncedHandler(functionValue, delay),
            subscribeTokenCounterStreamUpdates: (listener) => page.turnRuntime.requireStreaming().subscribeStreamUpdates(listener)
        },
        ws: {
            sendMessage: (payload, options) => sendWebSocketMessage(payload, options)
        }
    });
    return controller;
};

export { createChatTokenCounter };
export type { ChatTokenCounterDependencies };
