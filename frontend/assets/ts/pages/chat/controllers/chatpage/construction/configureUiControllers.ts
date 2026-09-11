/* SoAI - Chat page configure UI controllers [frontend/assets/ts/pages/chat/controllers/chatpage/construction/configureUiControllers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { CHAT_CONFIGURATION_MODAL_ID, isChatConversationSettingsWritable } from '@features/chat/public.ts';
import { ChatConfigurationController } from '@pages/chat/controllers/chatconfigurationcontroller/ChatConfigurationController.ts';
import { applyWidescreenMode, createChatUiBehaviorsHost, type UiBehaviorHost } from '@pages/chat/controllers/chatUiBehaviors.ts';
import { CHAT_SIDEBAR_OVERLAY_BREAKPOINT_PX } from '@pages/chat/contracts/constants.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatPreferencesManager } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';
import type { ChatConversationViewController } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatConversationState } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsState } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewState } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatRuntimeServices } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatComposerController } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatPagePresentationController } from '@pages/chat/controllers/chatpage/presentation/ChatPagePresentationController.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import { persistStagedConversationConfiguration } from '@pages/chat/controllers/chatpage/construction/StagedConversationConfigurationDomain.ts';
import { persistStagedConfigurationPreferences } from '@pages/chat/controllers/chatpage/construction/StagedConfigurationPreferencesDomain.ts';

interface ChatUiRuntimeDependencies extends ChatConfigurationRuntimeOwner, ChatConversationRuntimeOwner {
    preferences: ChatPreferencesManager;
    conversationView: ChatConversationViewController;
    conversationState: ChatConversationState;
    settings: ChatSettingsState;
    viewState: ChatViewState;
    runtimeServices: ChatRuntimeServices;
    composer: ChatComposerController;
    presentation: ChatPagePresentationController;
    pageDom: PageDom;
    pageResources: PageResources;
    feedback: PageFeedback;
    pageContext: PageContext;
    dom: {
        toggleClass(target: string | Element, className: string, force: boolean | null, context?: Element): void;
        getDocument(): Document;
    };
    navigateWithQuery(page: string, query: Record<string, string>): void;
    updatePageActionsMenuState(): void;
}

const createUiBehaviorsHost = (page: ChatUiRuntimeDependencies) => {
    return createChatUiBehaviorsHost({
        presentation: {
            pageDom: page.pageDom,
            getCachedIcon: (name, iconOptions) => page.presentation.cachedIcon(name, iconOptions),
            updatePageActionsMenuState: () => page.updatePageActionsMenuState(),
            getViewportWidth: () => measureLayoutViewport(page.dom.getDocument()).width,
            isMobileSidebarViewport: () => measureLayoutViewport(page.dom.getDocument()).width <= CHAT_SIDEBAR_OVERLAY_BREAKPOINT_PX
        },
        persistence: {
            pageResources: page.pageResources,
            getStorage: () => page.settings.storage,
            getStorageManager: () => {
                if (!page.conversationRuntime.hasStorage()) {
                    throw new Error('ChatPage requires a storage manager');
                }
                return page.conversationRuntime.requireStorage();
            },
            getComposerDraftManager: () => page.composer.draftManager(),
            dom: page.dom,
            timers: page.runtimeServices.timers
        },
        conversations: {
            getSidebarOpen: () => page.viewState.sidebarOpen,
            setSidebarOpen: (open) => {
                page.viewState.sidebarOpen = open;
            },
            getShowFavoritesAtTop: () => page.viewState.showFavoritesAtTop,
            setShowFavoritesAtTop: (show) => {
                page.viewState.showFavoritesAtTop = show;
            },
            getCurrentConversationId: () => page.conversationState.currentConversationId,
            getConversationById: (conversationId) => {
                const conversation = page.conversationState.conversations.get(conversationId);
                return conversation === undefined ? null : conversation;
            },
            isConversationExecuting: (conversationId) => page.conversationView.isExecuting(conversationId),
            syncSidebarListVisibility: (visible) => page.conversationView.syncSidebarListVisibility(visible),
            refreshConversationsUI: () => {
                page.conversationView.refresh().catch((error): void => {
                    errorHandler.warn('ChatPage', 'Failed to refresh conversations UI from behaviors host', ensureError(error));
                });
            },
            toggleConversationFavoriteById: (conversationId) => page.conversationView.requireActions().toggleConversationFavoriteById(conversationId),
            getParameters: () => page.settings.parameters
        }
    });
};

const createConfigurationController = (page: ChatUiRuntimeDependencies, uiBehaviors: UiBehaviorHost): ChatConfigurationController => {
    const configurationModalRoot = requireModalPresenter().requireElement(CHAT_CONFIGURATION_MODAL_ID);
    return new ChatConfigurationController({
        host: {
            pageDom: page.pageDom,
            feedback: page.feedback,
            root: configurationModalRoot,
            modelControl: {
                pageDom: page.pageDom,
                pageContext: page.pageContext,
                getCachedIcon: (name, iconOptions) => page.presentation.cachedIcon(name, iconOptions),
                isSelectionLocked: () => {
                    const conversation = page.conversationView.current();
                    return !isChatConversationSettingsWritable(conversation) || page.conversationView.isExecuting(conversation.id);
                },
                getCurrentConversation: () => page.conversationView.current(),
                isConversationExecuting: (conversationId) => page.conversationView.isExecuting(conversationId),
                navigateWithQuery: (pageId, query) => page.navigateWithQuery(pageId, query)
            },
            applyTextZoom: () => page.settings.applyTextZoom(),
            applyWidescreenMode: () => applyWidescreenMode(uiBehaviors),
            applyInputActionVisibility: () => page.composer.applyInputActionVisibility(),
            syncToolsEnabledToConversation: (enabled: boolean) => page.composer.syncToolsEnabled(enabled),
            syncToolApprovalRequiredToConversation: (required: boolean) => page.composer.syncToolApprovalRequired(required),
            persistParametersToConversation: () => page.composer.persistParameters(),
            prepareStagedConversationConfiguration: (configuration) => persistStagedConversationConfiguration(page, configuration, page.configurationRuntime.requireConversationSettings().conversationMutationPatch()),
            prepareStagedConfigurationPreferences: (parameters, model, isPresentationActive) => persistStagedConfigurationPreferences(page, parameters, model, isPresentationActive),
            persistBackendChatPreferences: () => page.preferences.persistBackend(),
            invalidateChatMarkup: (scope) => page.conversationView.invalidate(scope),
            renderCurrentConversation: () => page.conversationView.renderCurrent(),
            refreshConversationsUI: () => page.conversationView.refresh(),
            refreshChatWorkerRendering: () => page.conversationView.refreshWorkerRendering()
        },
        state: {
            getParameters: () => page.settings.parameters,
            setParameters: (parameters) => {
                page.settings.parameters = parameters;
            },
            getTextZoom: () => page.settings.textZoom,
            setTextZoom: (zoom) => {
                page.settings.textZoom = zoom;
            },
            getTextZoomController: () => page.settings.textZoomController,
            getStorageManager: () => {
                if (!page.conversationRuntime.hasStorage()) {
                    throw new Error('Chat configuration requires a storage manager');
                }
                return page.conversationRuntime.requireStorage();
            },
            getParameterManager: () => {
                if (!page.configurationRuntime.hasParameters()) {
                    throw new Error('Chat configuration requires a parameter manager');
                }
                return page.configurationRuntime.requireParameters();
            },
            isRichTextEnabled: () => page.settings.parameters.richTextEnabled === true,
            hasWritableCurrentConversation: () => isChatConversationSettingsWritable(page.conversationView.current()),
            getCurrentModel: () => page.conversationState.currentModel,
            setCurrentModel: (model) => {
                page.conversationState.currentModel = model;
            },
            getModels: () => page.conversationState.models,
            getModelIndex: () => page.conversationState.modelIndex,
            hasModelCatalog: () => page.conversationState.modelStreamHasPayload
        },
        headerActionContextId: 'chat-configuration'
    });
};

const configureChatUiRuntime = (page: ChatUiRuntimeDependencies): UiBehaviorHost => {
    const uiBehaviors = createUiBehaviorsHost(page);
    page.configurationRuntime.initializeConfiguration(createConfigurationController(page, uiBehaviors));
    return uiBehaviors;
};

export { configureChatUiRuntime };
export type { ChatUiRuntimeDependencies };
