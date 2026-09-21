/* SoAI - Chat lifecycle owner composition [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/ChatLifecycleComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModuleLogger } from '@core/moduleContext.ts';
import { ChatPageLifecycleController, type LifecycleControls } from '@pages/chat/controllers/chatpage/lifecycle/ChatPageLifecycleController.ts';
import { disposeChatPageLifecycle } from '@pages/chat/controllers/chatpage/lifecycle/dispose.ts';
import { bindChatPageRenderingPreferenceEvents } from '@pages/chat/controllers/chatpage/lifecycle/renderingPreferenceEventsController.ts';
import { ChatResponsiveLayoutSession } from '@pages/chat/controllers/chatpage/lifecycle/responsiveLayoutController.ts';
import type { ChatComposerController } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatPromptPickerController } from '@pages/chat/controllers/chatpage/composer/ChatPromptPickerController.ts';
import type { ChatCharacterMapController } from '@pages/chat/controllers/chatpage/composer/ChatCharacterMapController.ts';
import type { ChatConfigurationController } from '@pages/chat/controllers/chatpage/configuration/ChatConfigurationController.ts';
import type { ChatPreferencesManager } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import type { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';
import type { ChatConversationViewController } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import { setupDeterministicLifecycleForChatPage } from '@pages/chat/controllers/page/deterministicLifecycle.ts';
import { prepareChatPageInitialContent } from '@pages/chat/controllers/page/lifecycle.ts';
import { handleChatInitialModal } from '@pages/chat/controllers/initialModal.ts';
import type { ChatModelSessionManager } from '@pages/chat/controllers/chatpage/models/ChatModelSessionManager.ts';
import type { ChatPagePresentationController } from '@pages/chat/controllers/chatpage/presentation/ChatPagePresentationController.ts';
import type { ChatControllerRuntime } from '@pages/chat/controllers/chatpage/runtime/composeChatControllerRuntime.ts';
import type { ChatSessionDomainOwners, ChatSessionPageOwners, ChatSessionPlatformOwners } from '@pages/chat/controllers/chatpage/runtime/ChatSessionComposition.ts';
import type { ChatVoiceSession } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';
import type { UiBehaviorHost } from '@pages/chat/controllers/chatUiBehaviors.ts';

interface ChatLifecycleSessions {
    composer: ChatComposerController;
    configuration: ChatConfigurationController;
    conversationView: ChatConversationViewController;
    modelSession: ChatModelSessionManager;
    preferences: ChatPreferencesManager;
    presentation: ChatPagePresentationController;
    promptPicker: ChatPromptPickerController;
    characterMap: ChatCharacterMapController;
    toolbar: ChatConversationToolbarManager;
    voiceSession: ChatVoiceSession;
}

interface ChatLifecycleComposition {
    domain: ChatSessionDomainOwners;
    page: ChatSessionPageOwners;
    platform: ChatSessionPlatformOwners;
    sessions: ChatLifecycleSessions;
    controllerRuntime: ChatControllerRuntime;
    uiBehaviors: UiBehaviorHost;
    controls: LifecycleControls;
    initializeTokenCounter(): void;
}

const composeChatLifecycle = (composition: ChatLifecycleComposition, logger: ModuleLogger): ChatPageLifecycleController => {
    const { domain, page, platform, sessions, controllerRuntime, uiBehaviors, controls } = composition;
    const responsiveLayout = new ChatResponsiveLayoutSession({
        conversationState: domain.conversationState,
        settings: domain.settings,
        runtimeServices: domain.runtimeServices,
        uiBehaviors,
        conversationView: sessions.conversationView,
        modelSession: sessions.modelSession,
        taskScope: domain.taskScope,
        pageDom: page.pageDom,
        document: platform.dom.getDocument()
    });
    return new ChatPageLifecycleController(
        {
            composer: sessions.composer,
            composerSurface: domain.composerSurface,
            configurationSession: sessions.configuration,
            controllerInitialization: {
                ensureInitialized: () => controllerRuntime.initialization.ensureInitialized(controllerRuntime.messageSending),
                dispatch: (action, actionElement, event) => controllerRuntime.initialization.dispatch(action, actionElement, event),
                requireActionHost: () => controllerRuntime.initialization.requireActionHost(),
                dispose: () => controllerRuntime.initialization.dispose()
            },
            conversationRuntime: domain.conversationRuntime,
            conversationState: domain.conversationState,
            conversationToolbarSession: sessions.toolbar,
            conversationView: sessions.conversationView,
            getDomContext: () => page.pageHost.getContext(),
            lifecycleResources: domain.lifecycleResources,
            modelSession: sessions.modelSession,
            operations: {
                initializeTokenCounter: composition.initializeTokenCounter,
                prepareInitialContent: (parameters, signal, chatLogger) =>
                    prepareChatPageInitialContent(
                        {
                            composerSurface: domain.composerSurface,
                            configurationRuntime: domain.configurationRuntime,
                            conversationRuntime: domain.conversationRuntime,
                            preferences: sessions.preferences,
                            conversationView: sessions.conversationView,
                            conversationState: domain.conversationState,
                            runtimeServices: domain.runtimeServices,
                            lifecycleResources: domain.lifecycleResources,
                            composer: sessions.composer,
                            modelSession: sessions.modelSession,
                            presentation: sessions.presentation,
                            uiBehaviors,
                            services: page.services,
                            feedback: page.feedback,
                            conversationToolbarSession: sessions.toolbar,
                            detachedWindowHost: controllerRuntime.detachedWindowHost,
                            initializeTokenCounterController: composition.initializeTokenCounter,
                            syncResponsiveLayout: () => responsiveLayout.sync(),
                            resolveInteractionFocus: (conversationId, focusNonce) => platform.api.webui.chat.interactions.focus(conversationId, focusNonce)
                        },
                        parameters,
                        signal,
                        chatLogger
                    ),
                createRootEventsHost: (signal) =>
                    setupDeterministicLifecycleForChatPage(
                        {
                            composerSurface: domain.composerSurface,
                            conversationRuntime: domain.conversationRuntime,
                            turnRuntime: domain.turnRuntime,
                            conversationState: domain.conversationState,
                            composer: sessions.composer,
                            settings: domain.settings,
                            viewState: domain.viewState,
                            runtimeServices: domain.runtimeServices,
                            taskScope: domain.taskScope,
                            conversationView: sessions.conversationView,
                            modelSession: sessions.modelSession,
                            presentation: sessions.presentation,
                            pageElements: page.pageElements,
                            pageLifecycle: page.pageLifecycle,
                            feedback: page.feedback,
                            uiBehaviors,
                            messageSending: controllerRuntime.messageSending,
                            conversationToolbarSession: sessions.toolbar,
                            getDomContext: () => page.pageHost.getContext(),
                            dom: platform.dom,
                            controllerInitialization: { dispatch: (action, actionElement, event) => controllerRuntime.initialization.dispatch(action, actionElement, event) }
                        },
                        signal,
                        false
                    ),
                bindLocalizationEvents: (signal) => bindChatPageRenderingPreferenceEvents({ conversationView: sessions.conversationView, taskScope: domain.taskScope, dom: platform.dom }, signal),
                handleInitialModal: () => handleChatInitialModal({ router: platform.router, configurationSession: sessions.configuration }),
                disposePage: () =>
                    disposeChatPageLifecycle({
                        composerSurface: domain.composerSurface,
                        configurationRuntime: domain.configurationRuntime,
                        conversationRuntime: domain.conversationRuntime,
                        turnRuntime: domain.turnRuntime,
                        conversationState: domain.conversationState,
                        viewState: domain.viewState,
                        lifecycleResources: domain.lifecycleResources,
                        runtimeServices: domain.runtimeServices,
                        taskScope: domain.taskScope,
                        conversationView: sessions.conversationView,
                        modelSession: sessions.modelSession,
                        composer: sessions.composer,
                        pageDom: page.pageDom,
                        messageSending: controllerRuntime.messageSending,
                        configurationSession: sessions.configuration,
                        conversationToolbarSession: sessions.toolbar,
                        promptPickerSession: sessions.promptPicker,
                        characterMapSession: sessions.characterMap
                    }),
                acquireStreamPresentation: () => domain.runtimeServices.chatStream.acquirePresentation(),
                resumeStreamPresentation: () => domain.turnRuntime.requireStreaming().resumePresentation(),
                suspendStreamPresentation: () => {
                    if (domain.turnRuntime.hasStreaming()) {
                        domain.turnRuntime.requireStreaming().suspendPresentation();
                    }
                }
            },
            pageDom: page.pageDom,
            responsiveLayout,
            runtimeServices: domain.runtimeServices,
            services: page.services,
            settings: domain.settings,
            taskScope: domain.taskScope,
            turnRuntime: domain.turnRuntime,
            voiceSession: sessions.voiceSession
        },
        controls,
        logger
    );
};

export { composeChatLifecycle };
export type { ChatLifecycleComposition, ChatLifecycleSessions };
