/* SoAI - Chat page dispose [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/dispose.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS, disposeChatController } from '@features/chat/public.ts';
import { disposeActivityDurationLifecycle } from '@pages/chat/controllers/chatpage/lifecycle/activityDurationLifecycleRuntime.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatConfigurationController } from '@pages/chat/controllers/chatpage/configuration/ChatConfigurationController.ts';
import type { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';
import type { ChatPromptPickerController } from '@pages/chat/controllers/chatpage/composer/ChatPromptPickerController.ts';
import type { ChatCharacterMapController } from '@pages/chat/controllers/chatpage/composer/ChatCharacterMapController.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatLifecycleResourcesHost } from '@pages/chat/state/ChatLifecycleResourceManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { ChatMessageSendingOwner } from '@pages/chat/controllers/chatmessagesendingcontroller/ChatMessageSendingController.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';

interface ChatPageDisposeSource extends ChatComposerSurfaceRuntimeOwner, ChatConfigurationRuntimeOwner, ChatConversationRuntimeOwner, ChatTurnRuntimeOwner, ChatConversationStateHost, ChatViewStateHost, ChatLifecycleResourcesHost, ChatRuntimeServicesHost, ChatUiTaskScopeHost, ChatConversationViewHost, ChatModelSessionHost, ChatComposerHost, PageDomOwnerHost, ChatMessageSendingOwner {
    configurationSession: ChatConfigurationController;
    conversationToolbarSession: ChatConversationToolbarManager;
    promptPickerSession: ChatPromptPickerController;
    characterMapSession: ChatCharacterMapController;
}

const disposePrimaryControllerGroup = (page: ChatPageDisposeSource): void => {
    disposeActivityDurationLifecycle(page);
    page.turnRuntime.disposeStreamingAndConversationInputs();
    page.composer.disposeDraft();
    page.composer.disposeElicitation();
    page.messageSending.dispose();
    page.composerSurface.disposeAttachments();
    page.composer.disposeTokenCounter();
    page.viewState.searchBar = disposeChatController(page.viewState.searchBar);
};

const disposeUiControllerGroup = (page: ChatPageDisposeSource): void => {
    page.composerSurface.disposeUi();
    page.conversationRuntime.disposeMessages();
    page.configurationRuntime.disposeConversationSettings();
    page.conversationToolbarSession.dispose();
    page.promptPickerSession.dispose();
    page.modelSession.dispose();
    page.lifecycleResources.detachAction = disposeChatController(page.lifecycleResources.detachAction);
};

const disposeChatPageLifecycle = (page: ChatPageDisposeSource): void => {
    page.characterMapSession.dispose();
    page.taskScope.dispose();
    page.configurationSession.dispose();
    page.configurationRuntime.requireConfiguration().dispose();
    disposePrimaryControllerGroup(page);
    page.pageDom.optional(CHAT_SELECTORS.SEARCH_CONTAINER)?.remove();
    page.viewState.searchUiHost = null;
    page.conversationRuntime.requireStorage().saveState(true);
    page.conversationRuntime.requireStorage().dispose();
    page.lifecycleResources.autoSaveCleanup?.();
    page.lifecycleResources.autoSaveCleanup = null;
    disposeUiControllerGroup(page);
    page.viewState.iconCache.clear();
    page.conversationView.dispose();
    page.lifecycleResources.presenceExit?.();
    page.lifecycleResources.presenceExit = null;
    page.lifecycleResources.activePresenceExit?.();
    page.lifecycleResources.activePresenceExit = null;
    page.lifecycleResources.presentationPresenceExit?.();
    page.lifecycleResources.presentationPresenceExit = null;
    page.lifecycleResources.terminalIndicatorsExit?.();
    page.lifecycleResources.terminalIndicatorsExit = null;
    page.lifecycleResources.terminalRenderAcknowledgerExit?.();
    page.lifecycleResources.terminalRenderAcknowledgerExit = null;
};

export { disposeChatPageLifecycle };
