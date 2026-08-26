/* SoAI - Chat page initializers state [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContract, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { ChatComposerDraftManager, ChatConversationInputsManager, ChatStorageManager, ChatStreamingController, preflightComparisonTurn, type ChatStreamingControllerDependencies } from '@features/chat/public.ts';
import type { ChatControllerInitializationContext } from '@pages/chat/controllers/chatpage/construction/initializers/contracts.ts';
import { setCurrentConversationIdForChatPage, setCurrentModelForChatPage } from '@pages/chat/controllers/chatpage/construction/stateTransitions.ts';
import { createChatStreamRenderCoordinator } from '@pages/chat/controllers/page/renderer/chatStreamRenderCoordinatorController.ts';
import { updateConversationRenderCacheEntry } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';

const initializeStorageManager = (page: ChatControllerInitializationContext): void => {
    if (page.runtime.conversationRuntime.hasStorage()) {
        return;
    }
    const conversationManager = page.runtime.conversationRuntime.requireConversation();
    page.runtime.conversationRuntime.initializeStorage(
        new ChatStorageManager(
            {
                storage: page.state.settings.storage,
                api: page.platform.api,
                state: {
                    getConversations: () => page.state.conversationState.conversations,
                    setConversations: (conversations) => {
                        if (conversations === page.state.conversationState.conversations) {
                            return;
                        }
                        page.state.conversationState.conversations.clear();
                        for (const [id, conversation] of conversations.entries()) {
                            page.state.conversationState.conversations.set(id, conversation);
                        }
                    },
                    getCurrentConversationId: () => page.state.conversationState.currentConversationId,
                    setCurrentConversationId: (conversationId) => {
                        setCurrentConversationIdForChatPage({ conversationState: page.state.conversationState, runtimeServices: page.state.runtimeServices, pageDom: page.page.pageDom, composer: page.sessions.composer, voiceSession: page.sessions.voiceSession }, conversationId);
                    },
                    getCurrentModel: () => page.state.conversationState.currentModel,
                    setCurrentModel: (modelId) => {
                        setCurrentModelForChatPage({ conversationState: page.state.conversationState, pageDom: page.page.pageDom, composer: page.sessions.composer }, modelId);
                    },
                    getParameters: () => page.state.settings.parameters,
                    setParameters: (parameters) => {
                        page.state.settings.parameters = parameters;
                    },
                    getSidebarOpen: () => page.state.viewState.sidebarOpen,
                    setSidebarOpen: (open) => {
                        page.state.viewState.sidebarOpen = open;
                    },
                    getShowFavoritesAtTop: () => page.state.viewState.showFavoritesAtTop,
                    setShowFavoritesAtTop: (show) => {
                        page.state.viewState.showFavoritesAtTop = show;
                    }
                },
                conversationManager,
                chatStreamService: page.state.runtimeServices.chatStream,
                isMobileSidebarViewport: () => page.sessions.uiBehaviors.presentation.isMobileSidebarViewport(),
                invalidateChatMarkup: (scope) => page.sessions.conversationView.invalidate(scope),
                refreshConversationListUI: () => page.sessions.taskScope.runAsync('chat:renderConversationList', () => page.sessions.conversationView.renderList()),
                refreshConversationMetadataUI: () => page.sessions.taskScope.runAsync('chat:refreshConversationMetadata', () => page.sessions.conversationView.refreshListAndHeader()),
                refreshConversationsUI: () => page.sessions.conversationView.refresh(),
                clearConversationSelection: () => page.sessions.conversationView.requireActions().clearConversationSelection(),
                handleConversationDeleted: (conversationId) => page.sessions.conversationView.requireActions().handleDeletedConversationEvent(conversationId),
                handleConversationSettingsAuthorityChanged: (conversationId) => page.sessions.conversationView.requireActions().handleConversationSettingsAuthorityChangedEvent(conversationId),
                stopStreaming: (reason) => page.runtime.turnRuntime.requireStreaming().stopStreaming(reason ? { reason } : {}),
                runWithBoundary: (name, functionValue) => page.page.pageLifecycle.run(name, functionValue),
                showNotification: (message, type) => page.page.feedback.show(message, type)
            },
            { errorHandler }
        )
    );
};

const initializeChatStreamingController = (page: ChatControllerInitializationContext): void => {
    if (page.runtime.turnRuntime.hasStreaming()) {
        return;
    }
    const uiManager = page.runtime.composerSurface.requireUi();
    const messageManager = page.runtime.conversationRuntime.requireMessages();
    const storageManager = page.runtime.conversationRuntime.requireStorage();
    const modelAvailability = page.state.conversationState.modelAvailability;
    if (!modelAvailability) {
        throw new Error('ChatPage requires model availability state');
    }
    const streamManagerDependencies: ChatStreamingControllerDependencies = {
        cancelAgentTurn: async (conversationId, turnId, options) => {
            return await page.platform.api.webui.chat.agent.cancelTurn(conversationId, turnId, options);
        },
        uiManager,
        messageManager,
        storageManager,
        chatStreamService: page.state.runtimeServices.chatStream,
        preflightComparisonTurn: (inputArguments) => preflightComparisonTurn(page.platform.api, inputArguments),
        conversations: page.state.conversationState.conversations,
        state: {
            getCurrentConversationId: () => page.state.conversationState.currentConversationId,
            getCurrentModel: () => page.state.conversationState.currentModel
        },
        getModelStreamHasPayload: () => modelAvailability.getModelStreamHasPayload(),
        isModelAvailable: (modelId) => modelAvailability.isModelAvailable(modelId),
        onStreamTerminalUpdate: (update) => {
            page.runtime.turnRuntime.requireConversationInputs().handleStreamTerminal(update.conversationId);
            page.sessions.voiceSession.handleStreamTerminalized(update);
            page.runtime.turnRuntime.requireAgent().handleStreamTerminalized(update);
            page.sessions.conversationView.syncSidebarStatus(update.conversationId, { scheduleConversationListRender: !update.conversationListRenderAlreadyScheduled });
            if (update.status === 'complete' || update.status === 'error') {
                page.sessions.conversationView.acknowledgeTerminalAttentionIfViewed(update.conversationId, update.assistantTimestamp);
            }
        },
        onStreamingStateChange: (conversationId) => {
            page.sessions.conversationView.syncSidebarStatus(conversationId, { scheduleConversationListRender: false });
        },
        presentation: {
            optionalUI: (selector, parent) => page.page.pageDom.optional(selector, parent),
            updateHTML: (element, html, options?: { escape?: boolean }) => page.page.pageDom.updateHtml(element, html, options),
            invalidateChatMarkup: (scope) => page.sessions.conversationView.invalidate(scope),
            renderCurrentConversation: () => page.sessions.conversationView.renderCurrent(),
            renderConversationList: () => page.sessions.taskScope.runAsync('chat:renderConversationList', () => page.sessions.conversationView.renderList()),
            onTerminalPostRenderCommitted: (conversationId, requestId) => {
                page.state.runtimeServices.chatStream.acknowledgeTerminalRenderSettled(conversationId, requestId);
            },
            updateConversationRenderCache: (conversationId, messageDomId, signature) => updateConversationRenderCacheEntry({ cache: page.state.viewState.conversationRenderCache, conversationId, messageDomId, signature })
        },
        reportRequestFailure: (error) => page.sessions.conversationView.reportFailure(error),
        getRequestParameters: () => page.state.settings.requestParameters(),
        getWorkingParameters: () => page.runtime.configurationRuntime.requireConfiguration().getWorkingParameters(),
        resolveAgentModeForConversation: (conversationId) => page.runtime.turnRuntime.requireAgent().resolveModeForConversation(conversationId),
        resolveAgentRunningTurnId: (conversationId) => page.runtime.turnRuntime.requireAgent().resolveRunningTurnId(conversationId),
        isAgentRenderingActive: (conversationId) => page.runtime.turnRuntime.requireAgent().isRenderingActive(conversationId),
        createStreamRenderRuntime: (context) => createChatStreamRenderCoordinator(context)
    };
    page.runtime.turnRuntime.initializeStreaming(new ChatStreamingController(streamManagerDependencies, { errorHandler }));
    if (page.state.lifecycleResources.terminalRenderAcknowledgerExit === null) {
        page.state.lifecycleResources.terminalRenderAcknowledgerExit = page.state.runtimeServices.chatStream.registerTerminalRenderAcknowledger();
    }
};

const initializeChatTerminalIndicators = (page: ChatControllerInitializationContext): void => {
    if (page.state.lifecycleResources.terminalIndicatorsExit !== null) {
        return;
    }
    page.state.lifecycleResources.terminalIndicatorsExit = page.state.runtimeServices.attention.subscribeTerminalIndicators(() => {
        page.sessions.conversationView.acknowledgeTerminalAttentionIfViewed(page.state.conversationState.currentConversationId);
        void page.sessions.taskScope
            .runAsync('chat:renderConversationList', () => page.sessions.conversationView.renderList())
            .catch((error) => {
                errorHandler.warn('ChatPage', 'Failed to render conversation list after terminal indicator update', error);
            });
    });
};

const initializeConversationInputsManager = (page: ChatControllerInitializationContext): void => {
    if (page.runtime.turnRuntime.hasConversationInputs()) {
        return;
    }
    const conversationInputsApi = page.platform.api.webui.chat.inputQueue;
    page.runtime.turnRuntime.initializeConversationInputs(
        new ChatConversationInputsManager({
            conversationInputsApi,
            getCurrentConversationId: () => page.state.conversationState.currentConversationId,
            logWarning: (message, error) => {
                errorHandler.warn('ConversationInputs', message, error);
            },
            updateInputQueuePreview: () => page.runtime.composerSurface.requireUi().updateInputQueuePreview(),
            reconcileSettledConversationInputs: async (conversationId) => await page.runtime.turnRuntime.requireStreaming().reconcileConversationInputSettlement(conversationId),
            subscribeConversationInputEvents: (listeners) =>
                subscribeManagedWebSocketContracts({
                    label: 'ConversationInputs',
                    events: [createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.chat.inputsChanged, handler: listeners.inputsChanged }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.chat.inputTerminal, handler: listeners.inputTerminal })]
                })
        })
    );
};

const requireChatInput = (page: ChatControllerInitializationContext): HTMLTextAreaElement => {
    const input = page.sessions.elements.getChatInputElement();
    if (input === null) {
        throw new Error('Chat composer input is not available');
    }
    return input;
};

const refreshComposerUi = (page: ChatControllerInitializationContext): void => {
    const input = requireChatInput(page);
    page.sessions.composer.resizeInput(input);
    page.runtime.composerSurface.requireUi().updateInputState();
    page.runtime.composerSurface.requireUi().updateInputQueuePreview();
    page.sessions.composer.updateEmptyStateInputHint();
    page.sessions.composer.refreshTokenCounterPreview();
};

const initializeComposerDraftManager = (page: ChatControllerInitializationContext): void => {
    if (page.sessions.composer.draftManager()) {
        return;
    }
    const attachmentManager = page.runtime.composerSurface.requireAttachments();
    const conversationManager = page.runtime.conversationRuntime.requireConversation();
    page.sessions.composer.initializeDraft(
        new ChatComposerDraftManager({
            api: page.platform.api.webui.chat.draft,
            getCurrentConversationId: () => page.state.conversationState.currentConversationId,
            isConversationPersisted: (conversationId) => conversationManager.isConversationPersisted(conversationId),
            readText: () => requireChatInput(page).value,
            readSourceText: () => page.runtime.composerSurface.requireSoaiLinkResolution().sourceForDisplayedText(requireChatInput(page).value),
            setText: (value) => {
                page.page.pageElements.setValue(requireChatInput(page), value, { attribute: 'value' });
            },
            attachmentManager,
            refreshComposerUi: () => refreshComposerUi(page),
            noteInputDraftChanged: (value) => page.sessions.composer.noteDraftChanged(value),
            validateSourceProjection: (text, sourceText, records) => page.runtime.composerSurface.requireSoaiLinkResolution().validateRestore(text, sourceText, records),
            restoreSourceProjection: (text, sourceText, records) => page.runtime.composerSurface.requireSoaiLinkResolution().restore(text, sourceText, records),
            showNotification: (message, type) => page.page.feedback.show(message, type),
            logWarning: (message, error) => errorHandler.warn('ComposerDraft', message, error),
            subscribeDraftChanged: (listener) => subscribeManagedWebSocketContract({ label: 'ComposerDraft', contract: WEBSOCKET_EVENT_CONTRACTS.chat.draftChanged, handler: listener }),
            setTimer: (functionValue, delay) => page.page.pageResources.setTimer(functionValue, delay),
            clearTimer: (timer) => page.page.pageResources.clearTimer(timer)
        })
    );
};

export { initializeStorageManager, initializeChatStreamingController, initializeChatTerminalIndicators, initializeConversationInputsManager, initializeComposerDraftManager };
