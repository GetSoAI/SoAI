/* SoAI - Chat page create models controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/createModelsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import { getModelStreamPayloadTimeoutMs } from '@pages/chat/contracts/chatPageSupport.ts';
import { ChatModelsController } from '@pages/chat/controllers/chatmodelscontroller/ChatModelsController.ts';
import { setCurrentModelForChatPage } from '@pages/chat/controllers/chatpage/construction/stateTransitions.ts';
import type { ChatConfigurationRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';

interface ChatModelsControllerDependencies extends ChatConversationViewHost, ChatConversationStateHost, ChatModelSessionHost, ChatComposerHost, PageStreamingOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost, PageDomOwnerHost {
    configurationRuntime: ChatConfigurationRuntime;
}

type ChatPageLogWarning = (message: string, error?: Error | JsonValue) => void;

const createChatModelsController = (page: ChatModelsControllerDependencies, logWarning: ChatPageLogWarning): ChatModelsController => {
    return new ChatModelsController({
        streamHost: {
            subscribeToData: (streamId, handler) => page.streaming.subscribeResourceValue(streamId, handler),
            ensureDataSubscriptions: () => page.streaming.ensureSubscriptions(),
            trackDisposable: (disposer) => page.pageResources.track(disposer),
            logWarn: (message, error): void => logWarning(message, error)
        },
        streamConfig: { streamId: MODELS, payloadTimeoutMs: getModelStreamPayloadTimeoutMs() },
        state: {
            getModels: () => page.conversationState.models,
            setModels: (models) => {
                page.conversationState.models = models;
            },
            getModelIndex: () => page.conversationState.modelIndex,
            setModelIndex: (index) => {
                page.conversationState.modelIndex = index;
            },
            getCurrentModel: () => page.conversationState.currentModel,
            setCurrentModel: (modelId) => {
                setCurrentModelForChatPage(page, modelId);
            },
            getModelStreamHasPayload: () => page.conversationState.modelStreamHasPayload,
            setModelStreamHasPayload: (hasPayload) => {
                page.conversationState.modelStreamHasPayload = hasPayload;
            }
        },
        conversationHost: {
            getCurrentConversation: () => page.conversationView.current(),
            invalidateChatMarkup: (scope) => page.conversationView.invalidate(scope),
            renderCurrentConversation: () => page.conversationView.renderCurrent()
        },
        callbacks: {
            updateModelUI: () => page.modelSession.updateUi(),
            notifyModelStreamUpdate: (models) => {
                page.configurationRuntime.optionalConversationSettings()?.handleModelStreamUpdate?.(models);
                page.configurationRuntime.optionalConfiguration()?.refreshModelControlPresentation();
            },
            notifyAmbiguousModelSelection: (modelKey) => {
                page.feedback.show(i18n.t('chat.models.ambiguousSelection', { model: modelKey }), 'warning');
            }
        }
    });
};

export { createChatModelsController };
export type { ChatModelsControllerDependencies };
