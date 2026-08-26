/* SoAI - Chat page state, session, controller, and lifecycle composition [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/composeChatPageRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModuleLogger } from '@core/moduleContext.ts';
import { ToolImageHydrationCoordinator } from '@features/chat/public.ts';
import { ChatPageModelAvailabilityController } from '@pages/chat/controllers/chatpage/construction/ChatPageModelAvailabilityController.ts';
import { createChatFoundation } from '@pages/chat/controllers/chatpage/construction/configureBase.ts';
import { configureChatUiRuntime } from '@pages/chat/controllers/chatpage/construction/configureUiControllers.ts';
import type { ChatPageLifecycleController } from '@pages/chat/controllers/chatpage/lifecycle/ChatPageLifecycleController.ts';
import { resizeChatInput } from '@pages/chat/controllers/page/dom/input.ts';
import { composeChatSessions, type ChatSessions } from '@pages/chat/controllers/chatpage/runtime/composeChatSessions.ts';
import type { ChatSessionDomainOwners, ChatSessionPageOwners, ChatSessionPlatformOwners } from '@pages/chat/controllers/chatpage/runtime/ChatSessionComposition.ts';
import { ChatUiTaskScopeManager } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import { ChatRuntimeServices, type ChatPageDependencies } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import { ComposerSoaiLinkResolutionManager } from '@pages/chat/controllers/chatmessagesendingcontroller/composerSoaiLinkResolutionManager.ts';

interface ChatPageRuntimeOwners {
    domain: Omit<ChatSessionDomainOwners, 'runtimeServices' | 'taskScope' | 'settings' | 'toolImages'>;
    page: ChatSessionPageOwners;
    platform: Omit<ChatSessionPlatformOwners, 'dom'> & {
        dom: typeof import('@core/dom/dom.ts').dom;
    };
}

interface ChatPageRuntimeComposition extends ChatSessions {
    settings: ChatSessionDomainOwners['settings'];
    runtimeServices: ChatRuntimeServices;
    uiBehaviors: import('@pages/chat/controllers/chatUiBehaviors.ts').UiBehaviorHost;
    taskScope: ChatUiTaskScopeManager;
    controllerInitialization: { ensureInitialized(): Promise<void> };
    detachedWindowHost: ReturnType<ChatSessions['composeControllerRuntime']>['detachedWindowHost'];
    messageSending: ReturnType<ChatSessions['composeControllerRuntime']>['messageSending'];
    lifecycle: ChatPageLifecycleController;
}

const composeChatPageRuntime = (owners: ChatPageRuntimeOwners, dependencies: ChatPageDependencies, logger: ModuleLogger): ChatPageRuntimeComposition => {
    const { domain, page, platform } = owners;
    const foundation = createChatFoundation({ storage: platform.storage, pageDom: page.pageDom, pageResources: page.pageResources, getDocumentElement: () => platform.dom.getDocumentElement() }, logger);
    const settings = foundation.settings;
    const runtimeServices = new ChatRuntimeServices(dependencies, foundation.timers);
    const taskScope = new ChatUiTaskScopeManager({ runWithBoundary: (operationId, task) => page.pageLifecycle.run(operationId, task), getCurrentConversationId: () => domain.conversationState.currentConversationId });
    domain.composerSurface.initializeSoaiLinkResolution(new ComposerSoaiLinkResolutionManager());
    const toolImages = new ToolImageHydrationCoordinator();
    domain.conversationState.modelAvailability = new ChatPageModelAvailabilityController({ getModelIndex: () => domain.conversationState.modelIndex, getModels: () => domain.conversationState.models, getModelStreamHasPayload: () => domain.conversationState.modelStreamHasPayload });
    const sessions = composeChatSessions(
        { conversationRuntime: domain.conversationRuntime, turnRuntime: domain.turnRuntime, composerSurface: domain.composerSurface, configurationRuntime: domain.configurationRuntime, conversationState: domain.conversationState, settings, viewState: domain.viewState, lifecycleResources: domain.lifecycleResources, runtimeServices, taskScope, toolImages },
        { pageDom: page.pageDom, pageElements: page.pageElements, pageResources: page.pageResources, pageLifecycle: page.pageLifecycle, layout: page.layout, streaming: page.streaming, services: page.services, feedback: page.feedback, pageHost: page.pageHost },
        { pageContext: platform.pageContext, stateManager: platform.stateManager, api: platform.api, router: platform.router, dom: platform.dom, storage: platform.storage },
        {
            resizeChatInput: (textarea) => resizeChatInput({ services: page.services, pageElements: page.pageElements, pageDom: page.pageDom, dom: platform.dom }, textarea)
        }
    );
    const uiBehaviors = configureChatUiRuntime({
        conversationRuntime: domain.conversationRuntime,
        configurationRuntime: domain.configurationRuntime,
        preferences: sessions.preferences,
        conversationView: sessions.conversationView,
        conversationState: domain.conversationState,
        settings,
        viewState: domain.viewState,
        runtimeServices,
        composer: sessions.composer,
        presentation: sessions.presentation,
        pageDom: page.pageDom,
        pageResources: page.pageResources,
        feedback: page.feedback,
        pageContext: platform.pageContext,
        dom: platform.dom,
        navigateWithQuery: (pageId, query) => platform.router.navigateWithQuery(pageId, query),
        updatePageActionsMenuState: () => page.layout.updatePageActions()
    });
    const controllerRuntime = sessions.composeControllerRuntime(uiBehaviors, logger);
    const lifecycle = sessions.composeLifecycle(controllerRuntime, uiBehaviors, { abortListeners: (reason) => page.pageLifecycle.abortListeners(reason), resetListenersAbortSignal: () => page.pageLifecycle.beginListeners(), attachViewportResize: (handler, options) => page.layout.attachViewportResize(handler, options) }, logger);
    const controllerInitialization = { ensureInitialized: () => controllerRuntime.initialization.ensureInitialized(controllerRuntime.messageSending) };
    return { ...sessions, settings, runtimeServices, uiBehaviors, taskScope, controllerInitialization, detachedWindowHost: controllerRuntime.detachedWindowHost, messageSending: controllerRuntime.messageSending, lifecycle };
};

export { composeChatPageRuntime };
export type { ChatPageRuntimeComposition };
