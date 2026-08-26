/* SoAI - Chat page deterministic lifecycle [frontend/assets/ts/pages/chat/controllers/page/deterministicLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAgentMode, normalizeConversationId, type ChatTurnAdmissionSnapshot } from '@features/chat/public.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';
import { setupChatRootEvents } from '@pages/chat/controllers/page/events/setup.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatConversationToolbarManager } from '@pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatComposerHost } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatModelSessionHost } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatUiBehaviorsOwner } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ChatMessageSendingOwner } from '@pages/chat/controllers/chatmessagesendingcontroller/ChatMessageSendingController.ts';

interface DeterministicLifecycleSource extends ChatComposerSurfaceRuntimeOwner, ChatConversationRuntimeOwner, ChatTurnRuntimeOwner, ChatConversationStateHost, ChatComposerHost, ChatSettingsStateHost, ChatViewStateHost, ChatRuntimeServicesHost, ChatUiTaskScopeHost, ChatConversationViewHost, ChatModelSessionHost, ChatPagePresentationHost, PageUiOwnerHost, PageLifecycleOwnerHost, PageFeedbackOwnerHost, ChatUiBehaviorsOwner, ChatMessageSendingOwner {
    conversationToolbarSession: ChatConversationToolbarManager;
    getDomContext(): Element | null;
    dom: { getData: (element: Element | null, key: string) => string | null };
    controllerInitialization: { dispatch(action: import('@features/chat/public.ts').ChatActionId, actionElement: HTMLElement, event: Event): void };
}

const setupDeterministicLifecycleForChatPage = (page: DeterministicLifecycleSource, signal: AbortSignal, includeClick: boolean = true): ChatRootEventsHost => {
    const rootElement = page.getDomContext();
    if (!(rootElement instanceof HTMLElement)) {
        throw new Error('ChatPage root container is not initialized');
    }
    const requireRoot = (): HTMLElement => rootElement;
    const requireRootElement = (selector: string): HTMLElement => {
        const element = dom.resolve(selector, requireRoot());
        if (!(element instanceof HTMLElement)) {
            throw new Error(`ChatPage requires HTMLElement for selector: ${selector}`);
        }
        return element;
    };
    const optionalRootElement = (selector: string): HTMLElement | null => {
        const element = dom.resolve(selector, requireRoot());
        if (element === null) {
            return null;
        }
        if (!(element instanceof HTMLElement)) {
            throw new Error(`ChatPage expected HTMLElement for selector: ${selector}`);
        }
        return element;
    };

    const handleMobileSidebarClickAway = (target: Element): void => {
        if (!page.viewState.sidebarOpen) {
            return;
        }
        if (!page.uiBehaviors.presentation.isMobileSidebarViewport()) {
            return;
        }
        const sidebar = optionalRootElement('.chat-sidebar');
        const toggle = optionalRootElement('.chat-sidebar-toggle-btn');
        if (!sidebar || !toggle) {
            return;
        }
        if (sidebar.contains(target) || toggle.contains(target)) {
            return;
        }
        page.viewState.sidebarOpen = false;
        void Promise.resolve(page.uiBehaviors.layout.applySidebarState()).catch((error) => {
            errorHandler.warn('ChatPage', 'Failed to apply the chat sidebar state', ensureError(error));
        });
        page.settings.storage.setChatSidebarOpen(false);
        page.conversationRuntime.requireStorage().saveState();
    };

    const eventsHost: ChatRootEventsHost = {
        shell: {
            ensureRootElement: (): HTMLElement => requireRoot(),
            dispatchDataAction: (action, actionElement, event) => page.controllerInitialization.dispatch(action, actionElement, event),
            handleChatMessageHoverChange: (messageId, hovering) => page.conversationRuntime.requireMessages().handleDeleteUndoHoverChange(messageId, hovering),
            handleAgentKeyDown: (event) => page.composer.handleAgentKeyDown(event),
            hideConversationColorPicker: () => page.presentation.hideConversationColorPicker(),
            collapseSidebarIfNarrowViewport: () => page.conversationView.requireActions().collapseSidebarIfNarrowViewport(),
            handleMobileSidebarClickAway,
            closeChatModelControlMenu: () => page.modelSession.closeControlMenu(),
            handleChatModelControlSearchInput: (input) => page.modelSession.handleControlSearchInput(input),
            showNotification: (message, type, duration) => page.feedback.show(message, type, duration),
            runUiTask: (operationId, task) => page.taskScope.run(operationId, task)
        },
        composer: {
            resizeChatInput: (element) => page.composer.resizeInput(element),
            updateInputState: () => page.composerSurface.requireUi().updateInputState(),
            updateEmptyStateInputHint: () => page.composer.updateEmptyStateInputHint(),
            resolveSoaiLinksFromInput: (input, inputValue) => page.messageSending.resolveSoaiLinksFromInput(input, inputValue),
            handleChatInputHistoryNavigation: (input, direction) => page.composer.handleInputHistoryNavigation(input, direction),
            draft: {
                noteChanged: (value) => page.composer.noteDraftChanged(value),
                flush: async (reason) => page.composer.flushDraft(reason, { keepalive: true })
            },
            applyParameterValueFromElement: (element) => page.composer.applyParameterValueFromElement(element),
            handleFileUpload: async (event) => page.messageSending.handleFileUpload(event),
            handleFolderUpload: async (event) => page.messageSending.handleFolderUpload(event),
            handleAgentModeSelectChange: (event) => {
                const select = event.target;
                if (!(select instanceof HTMLSelectElement)) {
                    throw new TypeError('Agent mode select change requires a select element');
                }
                const selectedValue = select.value;
                if (!isAgentMode(selectedValue)) {
                    throw new Error(`Agent mode select received an invalid mode value: ${selectedValue}`);
                }
                page.turnRuntime.requireAgent().handleModeSelect(selectedValue);
            },
            resolveSendMessageButton: () => {
                const actionButton = requireRootElement('.chat-action-btn');
                return actionButton instanceof HTMLButtonElement ? actionButton : null;
            },
            resolveComposerActionMode: () => page.composerSurface.requireUi().resolveComposerActionMode(),
            resolveCurrentTurnAdmission: (): ChatTurnAdmissionSnapshot | null => {
                const conversationId = normalizeConversationId(page.conversationState.currentConversationId);
                return conversationId ? page.turnRuntime.requireStreaming().getCachedTurnAdmission(conversationId) : null;
            },
            resolveSyncedCurrentTurnAdmission: async (): Promise<ChatTurnAdmissionSnapshot | null> => {
                const conversationId = normalizeConversationId(page.conversationState.currentConversationId);
                return conversationId ? await page.turnRuntime.requireStreaming().resolveSyncedTurnAdmission(conversationId, page.pageLifecycle.signal()) : null;
            },
            sendMessage: async (options) => page.messageSending.sendMessage(options),
            queueConversationInputFromComposer: async (intent: 'queued' | 'steer') => page.messageSending.queueConversationInputFromComposer(intent),
            getComposerAttachmentCount: () => page.composerSurface.optionalAttachments()?.getAttachments().length ?? 0,
            isCurrentConversationStreaming: () => {
                const conversationId = page.conversationState.currentConversationId;
                const normalizedConversationId = normalizeConversationId(conversationId);
                if (!normalizedConversationId) {
                    return false;
                }
                return page.conversationView.isExecuting(normalizedConversationId);
            }
        },
        messages: {
            resolveMessageIdForTarget: (target) => {
                const messageRoot = target.closest('.chat-message');
                return messageRoot instanceof Element ? page.dom.getData(messageRoot, 'id') : null;
            },
            saveEditedMessage: async (messageId) => page.conversationRuntime.requireMessages().handleMessageAction(messageId, 'edit-save', {})
        },
        conversations: {
            handleConversationTitleBlur: async (event) => page.conversationView.requireActions().handleConversationTitleBlur(event),
            handleConversationListTitleBlur: async (event) => page.conversationView.requireActions().handleConversationListTitleBlur(event),
            updateConversationRenameDraft: (value) => page.conversationView.requireActions().updateConversationRenameDraft(value),
            saveConversationTitleRename: async () => page.conversationView.requireActions().handleConversationTitleSave(),
            cancelConversationTitleRename: () => page.conversationView.requireActions().handleConversationTitleCancel(),
            saveConversationListTitleRename: async () => page.conversationView.requireActions().handleConversationListTitleSave(),
            cancelConversationListTitleRename: () => page.conversationView.requireActions().handleConversationListTitleCancel(),
            isConversationSelectionActive: () => page.conversationToolbarSession.isSelectionActive(),
            exitConversationSelectMode: () => page.conversationToolbarSession.exitSelectMode()
        }
    };

    setupChatRootEvents(eventsHost, signal, { includeClick });
    return eventsHost;
};

export { setupDeterministicLifecycleForChatPage };
