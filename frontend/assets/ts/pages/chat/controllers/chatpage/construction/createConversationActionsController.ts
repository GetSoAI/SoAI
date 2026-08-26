/* SoAI - Chat page create conversation actions controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/createConversationActionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ChatConversationActionsController } from '@pages/chat/controllers/chatconversationactionscontroller/ChatConversationActionsController.ts';
import { setCurrentConversationIdForChatPage, setCurrentModelForChatPage } from '@pages/chat/controllers/chatpage/construction/stateTransitions.ts';
import { captureConversationDeleteFallbackSnapshot, resolveConversationDeleteFallbackId, type ConversationDeleteFallbackSnapshot } from '@pages/chat/controllers/page/conversationListOrderingController.ts';
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
import type { ChatUiBehaviorsOwner } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';

interface ChatConversationActionsDependencies {
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
        modelSession: ChatModelSessionHost['modelSession'];
    };
    ui: {
        elements: ChatPageElementsHost['elements'];
        conversationView: ChatConversationViewHost['conversationView'];
        uiBehaviors: ChatUiBehaviorsOwner['uiBehaviors'];
        composer: ChatComposerHost['composer'];
        voiceSession: ChatVoiceSessionHost['voiceSession'];
    };
    page: {
        pageLifecycle: PageLifecycleOwnerHost['pageLifecycle'];
        pageDom: PageDomOwnerHost['pageDom'];
        feedback: PageFeedbackOwnerHost['feedback'];
    };
    taskScope: ChatUiTaskScopeHost['taskScope'];
}

const createChatConversationActionsController = (page: ChatConversationActionsDependencies): ChatConversationActionsController => {
    const { runtime, state, ui } = page;
    let notifySaveChanged = (): void => {};
    const controller = new ChatConversationActionsController({
        host: {
            workflow: {
                feedback: page.page.feedback,
                runWithBoundary: (name, functionValue) => page.page.pageLifecycle.run(name, functionValue),
                runUiTask: (operationId, task) => page.taskScope.run(operationId, task),
                notifySaveChanged: () => notifySaveChanged()
            },
            view: {
                getCurrentConversation: () => ui.conversationView.current(),
                prepareConversationMessages: (conversationId) => ui.conversationView.prepareMessages(conversationId),
                getConversationTitleElement: () => ui.elements.getConversationTitleElement(),
                getConversationTitleInputElement: () => ui.elements.getConversationTitleInputElement(),
                getConversationListTitleInputElement: () => ui.elements.getConversationListTitleInputElement(),
                refreshConversationsUI: () => ui.conversationView.refresh(),
                refreshConversationListAndHeader: () => ui.conversationView.refreshListAndHeader(),
                renderConversationList: () => ui.conversationView.renderList(),
                revealConversationInList: (conversationId) => ui.conversationView.revealInList(conversationId),
                renderCurrentConversation: () => ui.conversationView.renderCurrent(),
                flushDOMUpdates: () => page.page.pageDom.flush(),
                invalidateChatMarkup: (scope) => ui.conversationView.invalidate(scope),
                updateModelUI: () => state.modelSession.updateUi(),
                refreshParameterUI: () => {
                    runtime.configurationRuntime.optionalParameters()?.updateParameterUI?.();
                },
                refreshTokenCounterPreview: () => ui.composer.refreshTokenCounterPreview(),
                applyInputActionVisibility: () => ui.composer.applyInputActionVisibility(),
                applySidebarState: () => ui.uiBehaviors.layout.applySidebarState()
            },
            navigation: {
                replaceConversationRoute: (conversationId, options) => ui.conversationView.replaceRoute(conversationId, options),
                captureConversationDeleteFallbackSnapshot: (activeConversationId) => captureConversationDeleteFallbackSnapshot({ conversationRuntime: runtime.conversationRuntime, conversationState: state.conversationState, settings: state.settings, viewState: state.viewState }, activeConversationId),
                resolveConversationDeleteFallbackId: (snapshot: ConversationDeleteFallbackSnapshot, deletedConversationIds) => resolveConversationDeleteFallbackId(snapshot, deletedConversationIds, state.conversationState.conversations)
            }
        },
        state: {
            hasConversation: (conversationId) => state.conversationState.conversations.has(conversationId),
            getConversation: (conversationId) => state.conversationState.conversations.get(conversationId) ?? null,
            getConversations: () => state.conversationState.conversations,
            getCurrentConversationId: () => state.conversationState.currentConversationId,
            setCurrentConversationId: (conversationId) => {
                setCurrentConversationIdForChatPage({ conversationState: state.conversationState, runtimeServices: state.runtimeServices, pageDom: page.page.pageDom, composer: ui.composer, voiceSession: ui.voiceSession }, conversationId);
            },
            getSelectedConversationHydrationState: () => state.conversationState.selectedConversationHydrationState,
            setSelectedConversationHydrationState: (state) => {
                page.state.conversationState.selectedConversationHydrationState = state;
            },
            setCurrentModel: (modelId) => {
                setCurrentModelForChatPage({ conversationState: state.conversationState, pageDom: page.page.pageDom, composer: ui.composer }, modelId);
            },
            hasModels: () => state.conversationState.models.length > 0,
            resolveModelKey: (candidate) => state.modelSession.resolveKey(candidate),
            getParameters: () => state.settings.parameters,
            setParameters: (parameters) => {
                state.settings.parameters = parameters;
            },
            getSidebarOpen: () => state.viewState.sidebarOpen,
            setSidebarOpen: (open) => {
                state.viewState.sidebarOpen = open;
            },
            getViewportWidth: () => ui.uiBehaviors.presentation.getViewportWidth(),
            getConversationRenameState: () => state.conversationState.conversationRenameState,
            setConversationRenameState: (renameState) => {
                state.conversationState.conversationRenameState = renameState;
            }
        },
        conversationManager: runtime.conversationRuntime.requireConversation(),
        storageManager: runtime.conversationRuntime.requireStorage(),
        uiManager: runtime.composerSurface.requireUi(),
        chatStreamingController: runtime.turnRuntime.requireStreaming(),
        conversationSettingsManager: runtime.configurationRuntime.optionalConversationSettings(),
        getComposerDraftManager: () => ui.composer.draftManager(),
        getMessageDeleteManager: () => runtime.conversationRuntime.optionalMessages(),
        concurrencyScope: page.taskScope.concurrency
    });
    notifySaveChanged = (): void => controller.notifySaveChanged();
    return controller;
};

export { createChatConversationActionsController };
export type { ChatConversationActionsDependencies };
