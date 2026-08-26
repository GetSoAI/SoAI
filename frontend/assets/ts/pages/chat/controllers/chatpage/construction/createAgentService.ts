/* SoAI - Chat page create agent service [frontend/assets/ts/pages/chat/controllers/chatpage/construction/createAgentService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import type { SetButtonLoadingOptions } from '@core/state/UIStateManager.ts';
import { isChatConversationSettingsWritable, type ToolImageHydrationCoordinator } from '@features/chat/public.ts';
import { updateConversationRenderCacheEntry } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';
import { setCurrentConversationIdForChatPage, setCurrentModelForChatPage } from '@pages/chat/controllers/chatpage/construction/stateTransitions.ts';
import type { ChatPageAgentHost, ChatPageAgentService } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import { createChatPageAgentService } from '@pages/chat/controllers/chatpageagent/service.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatPageElementsHost } from '@pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';

interface ChatAgentServiceDependencies {
    runtime: {
        composerSurface: ChatComposerSurfaceRuntimeOwner['composerSurface'];
        configurationRuntime: ChatConfigurationRuntimeOwner['configurationRuntime'];
        conversationRuntime: ChatConversationRuntimeOwner['conversationRuntime'];
        turnRuntime: ChatTurnRuntimeOwner['turnRuntime'];
    };
    state: {
        conversationState: ChatConversationStateHost['conversationState'];
        settings: ChatSettingsStateHost['settings'];
        viewState: ChatViewStateHost['viewState'];
        runtimeServices: ChatRuntimeServicesHost['runtimeServices'];
    };
    sessions: {
        elements: ChatPageElementsHost['elements'];
        conversationView: ChatConversationViewHost['conversationView'];
        taskScope: ChatUiTaskScopeHost['taskScope'];
        composer: ChatComposerHost['composer'];
        voiceSession: ChatVoiceSessionHost['voiceSession'];
        presentation: ChatPagePresentationHost['presentation'];
    };
    page: {
        services: PageServicesOwnerHost['services'];
        pageLifecycle: PageLifecycleOwnerHost['pageLifecycle'];
        pageDom: PageDomOwnerHost['pageDom'];
        pageResources: PageResourcesOwnerHost['pageResources'];
        feedback: PageFeedbackOwnerHost['feedback'];
    };
    platform: {
        api: ChatPageAgentHost['conversation']['getApi'] extends () => infer T ? T : never;
        pageContext: { sanitizer: { attribute(value: string): string } };
        stateManager: { setButtonLoading(target: string | Element, loading: boolean, options?: SetButtonLoadingOptions): void };
        toolImages: ToolImageHydrationCoordinator;
    };
}

const createChatAgentService = (page: ChatAgentServiceDependencies): ChatPageAgentService => {
    const transitionHost = {
        conversationState: page.state.conversationState,
        runtimeServices: page.state.runtimeServices,
        pageDom: page.page.pageDom,
        composer: page.sessions.composer,
        voiceSession: page.sessions.voiceSession
    };
    return createChatPageAgentService({
        conversation: {
            getApi: () => page.platform.api,
            getConversations: () => page.state.conversationState.conversations,
            getCurrentConversation: () => page.sessions.conversationView.current(),
            getConversationById: (conversationId) => {
                const conversation = page.state.conversationState.conversations.get(conversationId);
                return conversation === undefined ? null : conversation;
            },
            getToolImageHydrationCoordinator: () => page.platform.toolImages,
            getCurrentConversationId: () => page.state.conversationState.currentConversationId,
            captureConversationActivationSnapshot: () => page.sessions.taskScope.captureConversationActivation(),
            isConversationActivationSnapshotCurrent: (activation, expectedConversationId) => page.sessions.taskScope.isConversationActivationCurrent(activation, expectedConversationId),
            setCurrentConversationId: (conversationId) => {
                setCurrentConversationIdForChatPage(transitionHost, conversationId);
            },
            replaceConversationRoute: (conversationId) => page.sessions.conversationView.replaceRoute(conversationId),
            switchConversationById: (conversationId) => page.sessions.conversationView.requireActions().switchConversationById(conversationId),
            refreshConversationsUI: () => page.sessions.conversationView.refresh(),
            loadConversationMessages: (conversationId, options) => page.runtime.conversationRuntime.requireStorage().loadConversationMessages(conversationId, options),
            getCurrentModel: () => page.state.conversationState.currentModel,
            setCurrentModel: (modelId): void => {
                setCurrentModelForChatPage(transitionHost, modelId);
            },
            manager: page.runtime.conversationRuntime.requireConversation(),
            isChatStreamingConversation: (conversationId) => page.sessions.conversationView.isStreaming(conversationId),
            isConversationExecuting: (conversationId) => page.sessions.conversationView.isExecuting(conversationId),
            syncConversationSidebarStatus: (conversationId) => page.sessions.conversationView.syncSidebarStatus(conversationId, { scheduleConversationListRender: true })
        },
        rendering: {
            messages: page.runtime.conversationRuntime.requireMessages(),
            getChatInput: () => page.sessions.elements.getChatInputElement(),
            clearChatInput: () => page.sessions.composer.clearInput(),
            queryDocumentUI: (selector) => page.sessions.elements.queryDocumentUI(selector),
            setButtonLoading: (target, loading, options) => page.platform.stateManager.setButtonLoading(target, loading, options),
            getCachedIcon: (iconName, options) => page.sessions.presentation.cachedIcon(iconName, options),
            sanitizeAttribute: (value) => page.platform.pageContext.sanitizer.attribute(value),
            scheduleStreamingTimelineRender: (conversationId, message) => page.runtime.turnRuntime.requireStreaming().scheduleTimelineActivityRender(message, conversationId),
            updateConversationRenderCache: (conversationId, messageDomId, signature) => updateConversationRenderCacheEntry({ cache: page.state.viewState.conversationRenderCache, conversationId, messageDomId, signature }),
            invalidateChatMarkup: (scope) => page.sessions.conversationView.invalidate(scope),
            rerenderCurrentConversation: () => page.sessions.conversationView.renderCurrent(),
            scheduleConversationRender: () => page.sessions.taskScope.runAsync('chat:renderCurrentConversation', () => page.sessions.conversationView.renderCurrent())
        },
        interaction: {
            hasClipboardSupport: () => page.page.services.hasClipboardSupport(),
            copyToClipboard: (text, options) => page.page.services.copyToClipboard(text, options),
            syncToolsEnabledParameterFromConversation: (conversationId) => {
                const conversation = page.state.conversationState.conversations.get(conversationId) ?? null;
                if (!isChatConversationSettingsWritable(conversation)) {
                    return;
                }
                const modelSettings = conversation.modelSettings;
                const toolsEnabled = modelSettings.mcp?.toolsEnabled;
                if (toolsEnabled === true || toolsEnabled === false) {
                    page.state.settings.parameters.toolsEnabled = toolsEnabled;
                }
            },
            handleCurrentConversationToolsLockStateChange: () => {
                page.runtime.configurationRuntime.optionalConversationSettings()?.handleCurrentConversationToolsLockStateChange();
            },
            refreshTokenCounterPreview: () => page.sessions.composer.refreshTokenCounterPreview(),
            updateInputState: () => page.runtime.composerSurface.requireUi().updateInputState(),
            updateParameterUI: () => page.runtime.configurationRuntime.requireParameters().updateParameterUI(),
            updateInputQueuePreview: () => page.runtime.composerSurface.requireUi().updateInputQueuePreview()
        },
        planBar: {
            isVisible: () => page.state.settings.storage.getChatPlanBarVisible(),
            setVisible: (visible) => page.state.settings.storage.setChatPlanBarVisible(visible)
        },
        workflow: {
            pageDom: page.page.pageDom,
            pageResources: page.page.pageResources,
            feedback: page.page.feedback,
            runWithBoundary: (scope, functionValue) => page.page.pageLifecycle.run(scope, functionValue),
            logWarning: (message, error) => errorHandler.warn('ChatPage', message, error)
        }
    });
};

export { createChatAgentService };
export type { ChatAgentServiceDependencies };
