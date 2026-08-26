/* SoAI - Chat page action handlers host contract [frontend/assets/ts/pages/chat/controllers/chatpage/construction/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatActionId, ChatPageApi } from '@features/chat/public.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatConfigurationController } from '@pages/chat/controllers/chatpage/configuration/ChatConfigurationController.ts';
import type { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';
import type { ChatPromptPickerController } from '@pages/chat/controllers/chatpage/composer/ChatPromptPickerController.ts';
import type { ChatCharacterMapController } from '@pages/chat/controllers/chatpage/composer/ChatCharacterMapController.ts';
import type { ChatPreferencesHost } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { ChatAvatarController } from '@pages/chat/controllers/chatpage/presentation/ChatAvatarController.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatUiBehaviorsOwner } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ChatConversationActionsControllerContract } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';
import type { ChatMessageSendingOwner } from '@pages/chat/controllers/chatmessagesendingcontroller/ChatMessageSendingController.ts';
import type { ChatVoiceSessionHost } from '@pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts';

interface ChatActionHandlerDependencies {
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
        conversationView: ChatConversationViewHost['conversationView'];
        modelSession: ChatModelSessionHost['modelSession'];
    };
    sessions: {
        composer: ChatComposerHost['composer'];
        taskScope: ChatUiTaskScopeHost['taskScope'];
        presentation: ChatPagePresentationHost['presentation'];
        uiBehaviors: ChatUiBehaviorsOwner['uiBehaviors'];
        voiceSession: ChatVoiceSessionHost['voiceSession'];
        configurationSession: ChatConfigurationController;
        conversationToolbarSession: ChatConversationToolbarManager;
        promptPickerSession: ChatPromptPickerController;
        characterMapSession: ChatCharacterMapController;
        avatar: ChatAvatarController;
        conversationActions: ChatConversationActionsControllerContract;
        messageSending: ChatMessageSendingOwner['messageSending'];
    };
    page: {
        services: PageServicesOwnerHost['services'];
        pageElements: PageUiOwnerHost['pageElements'];
        pageLifecycle: PageLifecycleOwnerHost['pageLifecycle'];
        pageDom: PageDomOwnerHost['pageDom'];
        pageResources: PageResourcesOwnerHost['pageResources'];
        feedback: PageFeedbackOwnerHost['feedback'];
    };
    platform: {
        api: ChatPageApi;
        router: { navigate(page: string): void | Promise<void>; navigateWithQuery(page: string, query: Record<string, string>): void | Promise<void> };
        dom: { getData(element: Element | null, key: string): string | null };
    };
    callbacks: {
        requireConversationIdFromElement(actionElement: HTMLElement, ancestorSelector: string | null): string;
        dispatchMessageAction(actionElement: HTMLElement, action: ChatActionId, event: Event): void;
    };
}

export type { ChatActionHandlerDependencies };
