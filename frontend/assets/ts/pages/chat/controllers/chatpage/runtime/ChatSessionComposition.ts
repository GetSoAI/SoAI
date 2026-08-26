/* SoAI - Chat session domain, page, platform, and behavior ownership contracts [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/ChatSessionComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { ToolImageHydrationCoordinator } from '@features/chat/public.ts';
import type { ChatPageStorageSource } from '@pages/chat/controllers/chatpage/construction/baseHost.ts';
import type { CharacterMapViewStateStorage } from '@pages/chat/controllers/modals/charactermap/state.ts';
import type { ChatModelSessionDependencies } from '@pages/chat/controllers/chatpage/models/ChatModelSessionManager.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatUiTaskScopeManager } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatControllerRuntimeDependencies } from '@pages/chat/controllers/chatpage/runtime/composeChatControllerRuntime.ts';
import type { ChatConversationState } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatLifecycleResources } from '@pages/chat/state/ChatLifecycleResourceManager.ts';
import type { ChatRuntimeServices } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatSettingsState } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewState } from '@pages/chat/state/ChatViewStateManager.ts';

interface ChatSessionDomainOwners extends ChatComposerSurfaceRuntimeOwner, ChatConfigurationRuntimeOwner, ChatConversationRuntimeOwner, ChatTurnRuntimeOwner {
    conversationState: ChatConversationState;
    settings: ChatSettingsState;
    viewState: ChatViewState;
    lifecycleResources: ChatLifecycleResources;
    runtimeServices: ChatRuntimeServices;
    taskScope: ChatUiTaskScopeManager;
    toolImages: ToolImageHydrationCoordinator;
}

interface ChatSessionPageOwners {
    pageDom: PageDom;
    pageElements: PageUi;
    pageResources: PageResources;
    pageLifecycle: PageLifecycle;
    layout: PageLayout;
    streaming: PageStreaming;
    services: PageServices;
    feedback: PageFeedback;
    pageHost: PageHost;
}

interface ChatSessionPlatformOwners {
    pageContext: PageContext;
    stateManager: ChatControllerRuntimeDependencies['agentComposition']['platform']['stateManager'] & ChatModelSessionDependencies['platform']['stateManager'];
    api: ApiClient;
    router: Router;
    dom: ChatControllerRuntimeDependencies['managerComposition']['platform']['dom'];
    storage: ChatPageStorageSource & CharacterMapViewStateStorage;
}

interface ChatSessionBehavior {
    resizeChatInput(textarea: Element): void;
}

export type { ChatSessionBehavior, ChatSessionDomainOwners, ChatSessionPageOwners, ChatSessionPlatformOwners };
