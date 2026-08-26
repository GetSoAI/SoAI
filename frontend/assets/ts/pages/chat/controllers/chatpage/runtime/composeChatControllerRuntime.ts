/* SoAI - Chat controller runtime composition [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/composeChatControllerRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModuleLogger } from '@core/moduleContext.ts';
import type { ApiClient } from '@core/api/service.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { isConversationAuthorityLocked } from '@core/chat/conversationAuthorityLock.ts';
import { ChatModelControlController } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlController.ts';
import { CHAT_MODEL_CONTROL_ROOT_SELECTOR } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlDomController.ts';
import { resolveEffectiveModelsForChatModelControl } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlStateManager.ts';
import { updateConversationModelSettingsForChatModelControl } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlSettingsUpdateManager.ts';
import { createChatPageActionRuntime } from '@pages/chat/controllers/chatpage/construction/createActionHandlers.ts';
import { createChatAgentService } from '@pages/chat/controllers/chatpage/construction/createAgentService.ts';
import { createChatConversationActionsController } from '@pages/chat/controllers/chatpage/construction/createConversationActionsController.ts';
import { createChatMessageSendingController } from '@pages/chat/controllers/chatpage/construction/createMessageSendingController.ts';
import type { ChatMessageSendingController } from '@pages/chat/controllers/chatmessagesendingcontroller/ChatMessageSendingController.ts';
import { createChatModelsController } from '@pages/chat/controllers/chatpage/construction/createModelsController.ts';
import { createChatVoiceCallController } from '@pages/chat/controllers/chatpage/construction/createVoiceCallController.ts';
import { ensureChatPageManagersInitialized } from '@pages/chat/controllers/chatpage/construction/initializers/effects.ts';
import { setCurrentConversationIdForChatPage, setCurrentModelForChatPage } from '@pages/chat/controllers/chatpage/construction/stateTransitions.ts';
import { applyWidescreenMode, type UiBehaviorHost } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { DetachedWindowHost } from '@pages/chat/controllers/detached/chatDetachedWindow.ts';
import { ChatControllerInitialization } from '@pages/chat/controllers/chatpage/runtime/ChatControllerInitialization.ts';
import type { ChatActionHandlerDependencies } from '@pages/chat/controllers/chatpage/construction/contracts.ts';
import type { ChatControllerInitializationContext } from '@pages/chat/controllers/chatpage/construction/initializers/contracts.ts';
import type { ChatComposerController } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatConversationViewController } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatModelSessionManager } from '@pages/chat/controllers/chatpage/models/ChatModelSessionManager.ts';
import type { ChatPageElementsManager } from '@pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts';
import type { ChatPagePresentationController } from '@pages/chat/controllers/chatpage/presentation/ChatPagePresentationController.ts';
import type { ChatComposerSurfaceRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatVoiceSession } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';
import type { ChatConversationState } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatRuntimeServices } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatSettingsState } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewState } from '@pages/chat/state/ChatViewStateManager.ts';

type ChatManagerComposition = Omit<ChatControllerInitializationContext, 'sessions'> & { sessions: Omit<ChatControllerInitializationContext['sessions'], 'messageSending'> };
type ChatAgentComposition = Parameters<typeof createChatAgentService>[0];

interface ChatControllerRuntimeDomain {
    composerSurface: ChatComposerSurfaceRuntime;
    configurationRuntime: ChatConfigurationRuntime;
    conversationRuntime: ChatConversationRuntime;
    turnRuntime: ChatTurnRuntime;
}

interface ChatControllerRuntimeState {
    conversationState: ChatConversationState;
    runtimeServices: ChatRuntimeServices;
    settings: ChatSettingsState;
    viewState: ChatViewState;
}

interface ChatControllerRuntimeSessions {
    composer: ChatComposerController;
    conversationView: ChatConversationViewController;
    elements: ChatPageElementsManager;
    modelSession: ChatModelSessionManager;
    presentation: ChatPagePresentationController;
    voiceSession: ChatVoiceSession;
}

interface ChatControllerRuntimePage {
    feedback: PageFeedback;
    pageDom: PageDom;
    pageElements: PageUi;
    pageLifecycle: PageLifecycle;
    pageResources: PageResources;
    uiBehaviors: UiBehaviorHost;
}

interface ChatControllerRuntimePlatform {
    api: ApiClient;
    dom: ChatManagerComposition['platform']['dom'];
    pageContext: PageContext;
    router: Router;
    streaming: PageStreaming;
}

interface ChatControllerActionComposition {
    conversationToolbarSession: ChatActionHandlerDependencies['sessions']['conversationToolbarSession'];
    promptPickerSession: ChatActionHandlerDependencies['sessions']['promptPickerSession'];
    characterMapSession: ChatActionHandlerDependencies['sessions']['characterMapSession'];
    avatar: ChatActionHandlerDependencies['sessions']['avatar'];
    callbacks: ChatActionHandlerDependencies['callbacks'];
}

interface ChatControllerRuntimeDependencies {
    actionComposition: ChatControllerActionComposition;
    agentComposition: ChatAgentComposition;
    domain: ChatControllerRuntimeDomain;
    managerComposition: ChatManagerComposition;
    page: ChatControllerRuntimePage;
    platform: ChatControllerRuntimePlatform;
    sessions: ChatControllerRuntimeSessions;
    state: ChatControllerRuntimeState;
}

interface ChatControllerRuntime {
    initialization: ChatControllerInitialization;
    detachedWindowHost: DetachedWindowHost;
    messageSending: ChatMessageSendingController;
}

const composeChatControllerRuntime = (composition: ChatControllerRuntimeDependencies, logger: ModuleLogger): ChatControllerRuntime => {
    const { actionComposition, agentComposition, domain, managerComposition, page, platform, sessions, state } = composition;
    const modelTransition = { conversationState: state.conversationState, pageDom: page.pageDom, composer: sessions.composer };
    const conversationTransition = { ...modelTransition, runtimeServices: state.runtimeServices, voiceSession: sessions.voiceSession };
    const initializeAgent = (): void => {
        const agent = createChatAgentService(agentComposition);
        domain.turnRuntime.initializeAgent(agent);
        agent.initialize();
    };
    const initialization = new ChatControllerInitialization({
        initializeManagers: (messageSending) => ensureChatPageManagersInitialized({ ...managerComposition, sessions: { ...managerComposition.sessions, messageSending } }, logger),
        initializeConversationActions: () => {
            sessions.conversationView.initializeActions(
                createChatConversationActionsController({
                    runtime: { conversationRuntime: domain.conversationRuntime, turnRuntime: domain.turnRuntime, composerSurface: domain.composerSurface, configurationRuntime: domain.configurationRuntime },
                    state: { conversationState: state.conversationState, settings: state.settings, viewState: state.viewState, runtimeServices: state.runtimeServices, modelSession: sessions.modelSession },
                    ui: { elements: sessions.elements, conversationView: sessions.conversationView, uiBehaviors: page.uiBehaviors, composer: sessions.composer, voiceSession: sessions.voiceSession },
                    page: { pageLifecycle: page.pageLifecycle, pageDom: page.pageDom, feedback: page.feedback },
                    taskScope: agentComposition.sessions.taskScope
                })
            );
        },
        initializeActionHandlers: (messageSending) => {
            const conversationActions = sessions.conversationView.requireActions();
            return createChatPageActionRuntime({
                runtime: { conversationRuntime: domain.conversationRuntime, turnRuntime: domain.turnRuntime, composerSurface: domain.composerSurface, configurationRuntime: domain.configurationRuntime },
                state: { preferences: managerComposition.state.preferences, conversationState: state.conversationState, settings: state.settings, viewState: state.viewState, runtimeServices: state.runtimeServices, conversationView: sessions.conversationView, modelSession: sessions.modelSession },
                sessions: { composer: sessions.composer, taskScope: agentComposition.sessions.taskScope, uiBehaviors: page.uiBehaviors, presentation: sessions.presentation, configurationSession: managerComposition.sessions.configurationSession, conversationToolbarSession: actionComposition.conversationToolbarSession, promptPickerSession: actionComposition.promptPickerSession, characterMapSession: actionComposition.characterMapSession, avatar: actionComposition.avatar, voiceSession: sessions.voiceSession, conversationActions, messageSending },
                page: { services: agentComposition.page.services, pageElements: page.pageElements, pageLifecycle: page.pageLifecycle, pageDom: page.pageDom, pageResources: page.pageResources, feedback: page.feedback },
                platform: { api: platform.api, router: platform.router, dom: platform.dom },
                callbacks: actionComposition.callbacks
            });
        },
        initializeVoiceCall: async (messageSending) => {
            if (!sessions.voiceSession.hasCall())
                await sessions.voiceSession.initializeCall(
                    createChatVoiceCallController({
                        conversationRuntime: domain.conversationRuntime,
                        turnRuntime: domain.turnRuntime,
                        elements: sessions.elements,
                        conversationState: state.conversationState,
                        settings: state.settings,
                        runtimeServices: state.runtimeServices,
                        conversationView: sessions.conversationView,
                        feedback: page.feedback,
                        messageSending,
                        voiceSession: sessions.voiceSession,
                        api: platform.api
                    })
                );
        },
        ensureToolIconsLoaded: () => state.runtimeServices.toolIcons.ensureLoaded(),
        initializeAgent,
        updateAgentUi: () => domain.turnRuntime.requireAgent().updateUiForCurrentConversation()
    });
    const models = createChatModelsController(
        {
            configurationRuntime: domain.configurationRuntime,
            conversationState: state.conversationState,
            conversationView: sessions.conversationView,
            modelSession: sessions.modelSession,
            composer: sessions.composer,
            streaming: platform.streaming,
            pageResources: page.pageResources,
            feedback: page.feedback,
            pageDom: page.pageDom
        },
        (message, error) => {
            logger('warn', message, error);
        }
    );
    const modelControl = new ChatModelControlController({
        pageDom: page.pageDom,
        pageContext: platform.pageContext,
        getCachedIcon: (name, options) => sessions.presentation.cachedIcon(name, options),
        get models() {
            return state.conversationState.models;
        },
        get modelIndex() {
            return state.conversationState.modelIndex;
        },
        get modelStreamHasPayload() {
            return state.conversationState.modelStreamHasPayload;
        },
        hasSelectableModels: () => state.conversationState.modelAvailability?.hasSelectableModels() === true,
        getCurrentConversation: () => sessions.conversationView.current(),
        navigateWithQuery: (targetPage, query) => platform.router.navigateWithQuery(targetPage, query),
        isModelSelectionLocked: () => {
            const conversation = sessions.conversationView.current();
            return isConversationAuthorityLocked(conversation) || (conversation !== null && sessions.conversationView.isExecuting(conversation.id));
        },
        resolveChatModelControlRoots: () => page.pageDom.query(CHAT_MODEL_CONTROL_ROOT_SELECTOR).filter((element): element is HTMLElement => element instanceof HTMLElement && element.dataset['scope'] !== 'configuration'),
        resolveModelControlOverlayBoundary: () => null,
        resolveEffectiveModels: () => resolveEffectiveModelsForChatModelControl({ conversation: sessions.conversationView.current(), fallbackModelId: state.conversationState.currentModel }),
        applyEffectiveModels: async (models) => {
            const conversation = sessions.conversationView.current();
            const current = resolveEffectiveModelsForChatModelControl({ conversation, fallbackModelId: state.conversationState.currentModel });
            if (models.primary !== current.primary) {
                setCurrentModelForChatPage(modelTransition, models.primary);
            }
            if (conversation) {
                await updateConversationModelSettingsForChatModelControl(
                    {
                        ensureConversationPersisted: async (candidate) => domain.conversationRuntime.requireConversation().ensureConversationPersisted(candidate),
                        updateConversationSettings: async (conversationId, patch) => domain.conversationRuntime.requireConversation().updateConversationSettings(conversationId, patch),
                        saveState: (force) => domain.conversationRuntime.requireStorage().saveState(force)
                    },
                    conversation,
                    models
                );
                return;
            }
            await managerComposition.state.preferences.persistBackend();
        },
        updateModelUI: () => sessions.modelSession.updateUi(),
        isConversationExecuting: (conversationId) => sessions.conversationView.isExecuting(conversationId)
    });
    sessions.modelSession.initializeModelControllers(models, modelControl);
    const messageSending = createChatMessageSendingController(
        {
            conversationRuntime: domain.conversationRuntime,
            turnRuntime: domain.turnRuntime,
            composerSurface: domain.composerSurface,
            elements: sessions.elements,
            conversationView: sessions.conversationView,
            conversationState: state.conversationState,
            composer: sessions.composer,
            settings: state.settings,
            runtimeServices: state.runtimeServices,
            modelSession: sessions.modelSession,
            presentation: sessions.presentation,
            pageElements: page.pageElements,
            pageLifecycle: page.pageLifecycle,
            pageDom: page.pageDom,
            pageResources: page.pageResources,
            feedback: page.feedback,
            pageContext: platform.pageContext,
            dom: platform.dom,
            api: platform.api
        },
        (owner) => initialization.ensureInitialized(owner)
    );
    const detachedWindowHost: DetachedWindowHost = {
        runtime: {
            isDetached: () => agentComposition.page.services.isDetached(),
            optionalUI: (selector, context) => page.pageDom.optional(selector, context),
            dom: { setStyle: (element, property, value) => platform.dom.setStyle(element, property, value) },
            flushComposerDraft: async (reason) => await sessions.composer.flushDraft(reason)
        },
        state: {
            hasConversation: (conversationId) => state.conversationState.conversations.has(conversationId),
            getCurrentConversationId: () => state.conversationState.currentConversationId,
            setCurrentConversationId: (conversationId) => setCurrentConversationIdForChatPage(conversationTransition, conversationId),
            getCurrentModel: () => state.conversationState.currentModel,
            setCurrentModel: (modelId) => setCurrentModelForChatPage(modelTransition, modelId),
            getSidebarOpen: () => state.viewState.sidebarOpen,
            setSidebarOpen: (open) => {
                state.viewState.sidebarOpen = open;
            },
            getTextZoom: () => state.settings.textZoom,
            setTextZoom: (zoom) => {
                state.settings.textZoom = zoom;
            },
            getSearchQuery: () => state.viewState.searchQuery,
            setSearchQuery: (query) => {
                state.viewState.setSearchQuery(query);
            },
            getParameters: () => state.settings.parameters,
            setParameters: (parameters) => {
                state.settings.parameters = parameters;
            }
        },
        presentation: {
            validateTextZoomValue: (zoom, contextMessage) => managerComposition.state.preferences.validateTextZoom(zoom, contextMessage),
            persistTextZoom: (zoom) => state.settings.textZoomController.persistZoom(zoom),
            applyTextZoom: () => state.settings.applyTextZoom(),
            applySidebarState: () => page.uiBehaviors.layout.applySidebarState(),
            applyWidescreenMode: () => applyWidescreenMode(page.uiBehaviors),
            updateModelUI: () => sessions.modelSession.updateUi(),
            getInputElement: () => (domain.composerSurface.hasUi() ? domain.composerSurface.requireUi().getElement('input') : null),
            noteChatInputDraftChanged: (value) => sessions.composer.noteDraftChanged(value),
            updateInputState: () => (domain.composerSurface.hasUi() ? domain.composerSurface.requireUi().updateInputState() : undefined),
            updateParameterUi: () => domain.configurationRuntime.optionalParameters()?.updateParameterUI(),
            updateSearchBar: (value) => state.viewState.searchBar?.setValue(value, false)
        }
    };
    return { initialization, detachedWindowHost, messageSending };
};

export { composeChatControllerRuntime };
export type { ChatControllerRuntime, ChatControllerRuntimeDependencies };
