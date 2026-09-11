/* SoAI - Chat domain session composition [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/composeChatSessions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModuleLogger } from '@core/moduleContext.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { SelectionState } from '@core/selection/state.ts';
import type { ChatActionId } from '@features/chat/public.ts';
import { ChatCharacterMapController } from '@pages/chat/controllers/chatpage/composer/ChatCharacterMapController.ts';
import { ChatComposerController } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import { ChatComposerInputController } from '@pages/chat/controllers/chatpage/composer/ChatComposerInputController.ts';
import { ChatPromptPickerController } from '@pages/chat/controllers/chatpage/composer/ChatPromptPickerController.ts';
import { ChatConfigurationController } from '@pages/chat/controllers/chatpage/configuration/ChatConfigurationController.ts';
import { ChatPreferencesManager } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import { createChatTokenCounter } from '@pages/chat/controllers/chatpage/construction/initializers/tokenCounter.ts';
import { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';
import { ChatConversationViewController } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatPageLifecycleController, LifecycleControls } from '@pages/chat/controllers/chatpage/lifecycle/ChatPageLifecycleController.ts';
import { ChatModelSessionManager } from '@pages/chat/controllers/chatpage/models/ChatModelSessionManager.ts';
import { ChatAvatarController } from '@pages/chat/controllers/chatpage/presentation/ChatAvatarController.ts';
import { ChatPageElementsManager } from '@pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts';
import { ChatPagePresentationController } from '@pages/chat/controllers/chatpage/presentation/ChatPagePresentationController.ts';
import { composeChatLifecycle } from '@pages/chat/controllers/chatpage/runtime/ChatLifecycleComposition.ts';
import type { ChatSessionBehavior, ChatSessionDomainOwners, ChatSessionPageOwners, ChatSessionPlatformOwners } from '@pages/chat/controllers/chatpage/runtime/ChatSessionComposition.ts';
import { composeChatControllerRuntime, type ChatControllerRuntime } from '@pages/chat/controllers/chatpage/runtime/composeChatControllerRuntime.ts';
import { ChatVoiceSession } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';
import type { UiBehaviorHost } from '@pages/chat/controllers/chatUiBehaviors.ts';
import { dispatchMessageAction, requireConversationIdFromElement } from '@pages/chat/controllers/page/state.ts';
import { ChatComparisonTurnNavigationController } from '@pages/chat/widgets/comparisonturn/ChatComparisonTurnNavigationController.ts';

interface ChatSessions {
    elements: ChatPageElementsManager;
    preferences: ChatPreferencesManager;
    conversationView: ChatConversationViewController;
    presentation: ChatPagePresentationController;
    avatar: ChatAvatarController;
    modelSession: ChatModelSessionManager;
    composer: ChatComposerController;
    configuration: ChatConfigurationController;
    toolbar: ChatConversationToolbarManager;
    promptPicker: ChatPromptPickerController;
    characterMap: ChatCharacterMapController;
    voiceSession: ChatVoiceSession;
    composeControllerRuntime(uiBehaviors: UiBehaviorHost, logger: ModuleLogger): ChatControllerRuntime;
    composeLifecycle(controllerRuntime: ChatControllerRuntime, uiBehaviors: UiBehaviorHost, controls: LifecycleControls, logger: ModuleLogger): ChatPageLifecycleController;
}

const composeChatSessions = (domain: ChatSessionDomainOwners, page: ChatSessionPageOwners, platform: ChatSessionPlatformOwners, behavior: ChatSessionBehavior): ChatSessions => {
    const elements = new ChatPageElementsManager({
        pageDom: page.pageDom,
        setUIValue: (target, value, options) => page.pageElements.setValue(target, value, options),
        getDocument: () => platform.dom.getDocument(),
        getParameters: () => domain.settings.parameters,
        getMicrophoneAudioState: () => domain.lifecycleResources.microphoneAudioState,
        setMicrophoneAudioState: (state) => {
            domain.lifecycleResources.microphoneAudioState = state;
        }
    });
    const presentation = new ChatPagePresentationController({ turnRuntime: domain.turnRuntime, conversationState: domain.conversationState, settings: domain.settings, viewState: domain.viewState, taskScope: domain.taskScope, feedback: page.feedback, services: page.services, pageElements: page.pageElements, pageDom: page.pageDom, dom: platform.dom });
    const comparisonNavigation = new ChatComparisonTurnNavigationController(domain.runtimeServices.timers);
    const conversationSelection = new SelectionState();
    const voiceSession = new ChatVoiceSession();
    const modelSession = new ChatModelSessionManager({
        runtime: { conversationRuntime: domain.conversationRuntime, turnRuntime: domain.turnRuntime, composerSurface: domain.composerSurface, configurationRuntime: domain.configurationRuntime },
        state: { conversationState: domain.conversationState, settings: domain.settings },
        page: { taskScope: domain.taskScope, pageDom: page.pageDom, streaming: page.streaming },
        platform: { dom: platform.dom, stateManager: platform.stateManager, getDomContext: () => page.pageHost.getContext() },
        comparisonNavigation
    });
    const conversationView = new ChatConversationViewController({
        conversationRuntime: domain.conversationRuntime,
        turnRuntime: domain.turnRuntime,
        composerSurface: domain.composerSurface,
        configurationRuntime: domain.configurationRuntime,
        conversationState: domain.conversationState,
        settings: domain.settings,
        viewState: domain.viewState,
        runtimeServices: domain.runtimeServices,
        taskScope: domain.taskScope,
        services: page.services,
        pageLifecycle: page.pageLifecycle,
        pageDom: page.pageDom,
        feedback: page.feedback,
        router: platform.router,
        pageContext: platform.pageContext,
        modelSession,
        presentation,
        conversationSelection
    });
    const avatar = new ChatAvatarController({ conversationView, settings: domain.settings, taskScope: domain.taskScope, pageDom: page.pageDom, feedback: page.feedback });
    const preferences = new ChatPreferencesManager({
        conversationRuntime: domain.conversationRuntime,
        composerSurface: domain.composerSurface,
        configurationRuntime: domain.configurationRuntime,
        conversationState: domain.conversationState,
        settings: domain.settings,
        conversationView,
        feedback: page.feedback,
        api: platform.api,
        subscribeAuthoritativePreferences: (eventName, listener) => {
            page.pageResources.on(platform.dom.getDocument().defaultView ?? platform.dom.getDocument(), eventName, listener);
        }
    });
    const composerInput = new ChatComposerInputController({ composerSurface: domain.composerSurface, elements, pageDom: page.pageDom, pageElements: page.pageElements, resize: behavior.resizeChatInput, taskScope: domain.taskScope });
    const composer = new ChatComposerController({
        runtime: { conversationRuntime: domain.conversationRuntime, turnRuntime: domain.turnRuntime, composerSurface: domain.composerSurface, configurationRuntime: domain.configurationRuntime },
        page: { pageDom: page.pageDom, feedback: page.feedback, services: page.services, pageElements: page.pageElements, getLifecycleSignal: () => page.pageLifecycle.signal() },
        state: { settings: domain.settings, conversationState: domain.conversationState },
        sessions: { taskScope: domain.taskScope, preferences, conversationView, presentation, voiceSession },
        platform: { api: platform.api, dom: platform.dom },
        input: composerInput
    });
    const configuration = new ChatConfigurationController({ composerSurface: domain.composerSurface, configurationRuntime: domain.configurationRuntime, conversationView, composer, taskScope: domain.taskScope, modelSession, presentation, layout: page.layout, services: page.services, pageDom: page.pageDom, feedback: page.feedback, api: platform.api, pageLifecycle: page.pageLifecycle, runtimeServices: domain.runtimeServices, settings: domain.settings });
    const toolbar = new ChatConversationToolbarManager({ conversationRuntime: domain.conversationRuntime, conversationView, conversationState: domain.conversationState, presentation, pageDom: page.pageDom, feedback: page.feedback, taskScope: domain.taskScope, pageContext: platform.pageContext, api: platform.api, conversationSelection });
    const promptPicker = new ChatPromptPickerController({ feedback: page.feedback, composer, presentation, api: platform.api, getDocument: () => platform.dom.getDocument(), requireStreamManager: () => page.streaming.runtime(), navigate: (page) => platform.router.navigate(page), taskScope: domain.taskScope });
    const characterMap = new ChatCharacterMapController({
        api: platform.api,
        composer,
        feedback: page.feedback,
        services: page.services,
        storage: platform.storage,
        requirePresenter: requireModalPresenter,
        getLifecycleSignal: () => domain.lifecycleResources.getAfterInitializeAbortController()?.signal ?? null,
        runTask: (operationId, task) => domain.taskScope.run(operationId, task)
    });
    const requireConversationId = (actionElement: HTMLElement, ancestorSelector: string | null): string => requireConversationIdFromElement(platform.dom, actionElement, ancestorSelector);
    const dispatchAction = (actionElement: HTMLElement, action: ChatActionId, event: Event): void => {
        dispatchMessageAction({ dom: platform.dom, runUiTask: (operationId, task) => domain.taskScope.run(operationId, task), messageManager: domain.conversationRuntime.requireMessages() }, actionElement, action, event);
    };
    const initializeTokenCounter = (): void => {
        if (composer.hasTokenCounter()) return;
        composer.initializeTokenCounter(createChatTokenCounter({ conversationRuntime: domain.conversationRuntime, turnRuntime: domain.turnRuntime, composerSurface: domain.composerSurface, conversationState: domain.conversationState, conversationView, settings: domain.settings, elements, taskScope: domain.taskScope, services: page.services, pageDom: page.pageDom, feedback: page.feedback }));
    };
    const composeControllerRuntime = (uiBehaviors: UiBehaviorHost, logger: ModuleLogger): ChatControllerRuntime =>
        composeChatControllerRuntime(
            {
                domain: { conversationRuntime: domain.conversationRuntime, turnRuntime: domain.turnRuntime, composerSurface: domain.composerSurface, configurationRuntime: domain.configurationRuntime },
                state: { conversationState: domain.conversationState, settings: domain.settings, runtimeServices: domain.runtimeServices, viewState: domain.viewState },
                sessions: { composer, conversationView, elements, modelSession, presentation, voiceSession },
                page: { feedback: page.feedback, pageDom: page.pageDom, pageElements: page.pageElements, pageLifecycle: page.pageLifecycle, pageResources: page.pageResources, uiBehaviors },
                platform: { api: platform.api, dom: platform.dom, pageContext: platform.pageContext, router: platform.router, streaming: page.streaming },
                agentComposition: {
                    runtime: { conversationRuntime: domain.conversationRuntime, turnRuntime: domain.turnRuntime, composerSurface: domain.composerSurface, configurationRuntime: domain.configurationRuntime },
                    state: { conversationState: domain.conversationState, settings: domain.settings, viewState: domain.viewState, runtimeServices: domain.runtimeServices },
                    sessions: { elements, conversationView, taskScope: domain.taskScope, composer, voiceSession, presentation },
                    page: { services: page.services, pageLifecycle: page.pageLifecycle, pageDom: page.pageDom, pageResources: page.pageResources, feedback: page.feedback },
                    platform: { api: platform.api, pageContext: platform.pageContext, stateManager: platform.stateManager, toolImages: domain.toolImages }
                },
                managerComposition: {
                    runtime: { conversationRuntime: domain.conversationRuntime, turnRuntime: domain.turnRuntime, composerSurface: domain.composerSurface, configurationRuntime: domain.configurationRuntime },
                    state: { preferences, conversationState: domain.conversationState, settings: domain.settings, viewState: domain.viewState, runtimeServices: domain.runtimeServices, lifecycleResources: domain.lifecycleResources },
                    sessions: { elements, conversationView, composer, taskScope: domain.taskScope, modelSession, presentation, configurationSession: configuration, voiceSession, uiBehaviors },
                    page: { services: page.services, pageLifecycle: page.pageLifecycle, pageResources: page.pageResources, feedback: page.feedback, pageDom: page.pageDom, pageElements: page.pageElements },
                    platform: { pageContext: platform.pageContext, dom: platform.dom, api: platform.api, toolImages: domain.toolImages },
                    pageId: 'chat'
                },
                actionComposition: {
                    conversationToolbarSession: toolbar,
                    promptPickerSession: promptPicker,
                    characterMapSession: characterMap,
                    avatar,
                    callbacks: {
                        requireConversationIdFromElement: requireConversationId,
                        dispatchMessageAction: dispatchAction
                    }
                }
            },
            logger
        );
    const composeLifecycle = (controllerRuntime: ChatControllerRuntime, uiBehaviors: UiBehaviorHost, controls: LifecycleControls, logger: ModuleLogger): ChatPageLifecycleController => composeChatLifecycle({ domain, page, platform, sessions: { composer, configuration, conversationView, modelSession, preferences, presentation, promptPicker, characterMap, toolbar, voiceSession }, controllerRuntime, uiBehaviors, controls, initializeTokenCounter }, logger);
    return { elements, preferences, conversationView, presentation, avatar, modelSession, composer, configuration, toolbar, promptPicker, characterMap, voiceSession, composeControllerRuntime, composeLifecycle };
};

export { composeChatSessions };
export type { ChatSessions };
