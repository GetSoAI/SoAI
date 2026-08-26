/* SoAI - Chat page initializers contracts [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DOMTarget, SetHTMLOptions } from '@core/dom/dom.ts';
import type { ModuleLogger } from '@core/moduleContext.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ChatMessageManagerDependencies, ChatPageApi, ChatStreamingControllerDependencies, ToolImageHydrationCoordinator } from '@features/chat/public.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatPageElementsHost } from '@pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts';
import type { ChatPreferencesHost } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatLifecycleResourcesHost } from '@pages/chat/state/ChatLifecycleResourceManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatUiBehaviorsOwner } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ChatMessageSendingOwner } from '@pages/chat/controllers/chatmessagesendingcontroller/ChatMessageSendingController.ts';
import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';

type Logger = ModuleLogger;
interface ChatControllerInitializationContext {
    runtime: {
        composerSurface: ChatComposerSurfaceRuntimeOwner['composerSurface'];
        configurationRuntime: ChatConfigurationRuntimeOwner['configurationRuntime'];
        conversationRuntime: ChatConversationRuntimeOwner['conversationRuntime'];
        turnRuntime: ChatTurnRuntimeOwner['turnRuntime'];
    };
    state: {
        preferences: ChatPreferencesHost['preferences'];
        conversationState: ChatConversationStateHost['conversationState'];
        settings: ChatSettingsStateHost['settings'];
        viewState: ChatViewStateHost['viewState'];
        runtimeServices: ChatRuntimeServicesHost['runtimeServices'];
        lifecycleResources: ChatLifecycleResourcesHost['lifecycleResources'];
    };
    sessions: {
        elements: ChatPageElementsHost['elements'];
        conversationView: ChatConversationViewHost['conversationView'];
        composer: ChatComposerHost['composer'];
        taskScope: ChatUiTaskScopeHost['taskScope'];
        modelSession: ChatModelSessionHost['modelSession'];
        presentation: ChatPagePresentationHost['presentation'];
        configurationSession: import('@pages/chat/controllers/chatpage/configuration/ChatConfigurationController.ts').ChatConfigurationController;
        messageSending: ChatMessageSendingOwner['messageSending'];
        voiceSession: ChatVoiceSessionHost['voiceSession'];
        uiBehaviors: ChatUiBehaviorsOwner['uiBehaviors'];
    };
    page: {
        services: PageServicesOwnerHost['services'];
        pageLifecycle: PageLifecycleOwnerHost['pageLifecycle'];
        pageResources: PageResourcesOwnerHost['pageResources'];
        feedback: PageFeedbackOwnerHost['feedback'];
        pageDom: PageDomOwnerHost['pageDom'];
        pageElements: PageUiOwnerHost['pageElements'];
    };
    platform: {
        pageContext: { sanitizer: SanitizerApi };
        dom: {
            getDocument: () => Document;
            getData: (element: Element | null, key: string) => string | null;
            setHTML: (target: DOMTarget, html: TrustedHtml | string, options?: SetHTMLOptions) => void;
            setStyle: (element: HTMLElement, prop: string, value: string | null) => void;
        };
        api: ChatPageApi;
        toolImages: ToolImageHydrationCoordinator;
    };
    pageId: string;
}

export type { ChatControllerInitializationContext, ChatStreamingControllerDependencies, ChatMessageManagerDependencies, Logger };
export type { ChatPreferencesManager, ConversationSettingsHost } from '@features/chat/public.ts';
