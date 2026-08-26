/* SoAI - Chat page toolbar wiring [frontend/assets/ts/pages/chat/controllers/chatpage/construction/toolbarWiring.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { parseBackendConversationRecord, type Conversation, type ChatPageApi } from '@features/chat/public.ts';
import type { WebuiConversationResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import { executeBatchArchive, executeBatchClone, executeBatchDelete } from '@pages/chat/widgets/conversationtoolbar/batchOperations.ts';
import { ConversationSelectionManager } from '@pages/chat/widgets/conversationtoolbar/selectionManager.ts';
import { ConversationToolbarController } from '@pages/chat/widgets/conversationtoolbar/toolbarController.ts';
import type { ConversationToolbarUiRefs } from '@pages/chat/widgets/conversationtoolbar/types.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { SelectionState } from '@core/selection/state.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatPagePresentationHost } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface ToolbarWiringHost extends ChatConversationRuntimeOwner, ChatConversationViewHost, ChatConversationStateHost, ChatPagePresentationHost, PageDomOwnerHost, PageFeedbackOwnerHost {
    api: ChatPageApi;
}

const requireToolbarButton = (host: ToolbarWiringHost, selector: string): HTMLButtonElement => {
    const element = host.pageDom.requireHTMLElement(selector);
    if (!(element instanceof HTMLButtonElement)) {
        throw new TypeError(`Toolbar element ${selector} must be a button element`);
    }
    return element;
};

const resolveToolbarUiRefs = (host: ToolbarWiringHost): ConversationToolbarUiRefs => {
    return {
        toolbarContainer: host.pageDom.requireHTMLElement('#chat-toolbar-container'),
        collapsedLayer: host.pageDom.requireHTMLElement('.chat-toolbar-collapsed-layer'),
        expandedLayer: host.pageDom.requireHTMLElement('.chat-toolbar-expanded-layer'),
        toolbarContent: host.pageDom.requireHTMLElement('.chat-toolbar-content'),
        metricsContainer: host.pageDom.requireHTMLElement('.chat-toolbar-metrics'),
        totalConversationsLabel: host.pageDom.requireHTMLElement('.chat-toolbar-total-conversations'),
        totalConversationsIcon: host.pageDom.requireHTMLElement('.chat-toolbar-total-conversations-icon'),
        openArchivedButton: requireToolbarButton(host, '.chat-toolbar-open-archived-btn'),
        selectButton: host.pageDom.requireHTMLElement('.chat-toolbar-select-btn'),
        batchActionsContainer: host.pageDom.requireHTMLElement('.chat-toolbar-batch-actions'),
        selectedCountLabel: host.pageDom.requireHTMLElement('.chat-toolbar-selected-count'),
        batchArchiveButton: requireToolbarButton(host, '.chat-toolbar-batch-archive-btn'),
        batchCloneButton: requireToolbarButton(host, '.chat-toolbar-batch-clone-btn'),
        batchDeleteButton: requireToolbarButton(host, '.chat-toolbar-batch-delete-btn'),
        exitSelectButton: host.pageDom.requireHTMLElement('.chat-toolbar-exit-select-btn'),
        collapsedChevronToggle: host.pageDom.requireHTMLElement('.chat-toolbar-toggle'),
        expandedChevronToggle: host.pageDom.requireHTMLElement('.chat-toolbar-expanded-toggle'),
        conversationsList: host.pageDom.requireHTMLElement('#conversations-list')
    };
};

const runBatchArchiveForPage = async (host: ToolbarWiringHost, controller: ConversationToolbarController): Promise<void> => {
    const conversationManager = host.conversationRuntime.requireConversation();
    const sharedDependencies = createBatchOperationSharedDependencies(host, controller);
    const selectedIds = controller.selection.list();
    await executeBatchArchive(
        {
            ...sharedDependencies,
            setArchived: (conversationId, isArchived) => conversationManager.setArchived(conversationId, isArchived)
        },
        selectedIds
    );
};

const initializeConversationToolbarForPage = (host: ToolbarWiringHost, selectionState: SelectionState): ConversationToolbarController => {
    const selection = new ConversationSelectionManager(
        {
            renderConversationList: () => host.conversationView.renderList()
        },
        selectionState
    );
    const controller = new ConversationToolbarController(
        {
            getConversations: () => host.conversationState.conversations,
            getIconHtml: (name, options) => host.presentation.cachedIcon(name, options)
        },
        selection
    );
    const refs = resolveToolbarUiRefs(host);
    controller.bindUi(refs);
    controller.updateMetrics();
    return controller;
};

const createBatchOperationSharedDependencies = (host: ToolbarWiringHost, controller: ConversationToolbarController) => {
    const storageManager = host.conversationRuntime.requireStorage();
    return {
        conversations: host.conversationState.conversations,
        showNotification: (message: string, type: NotificationType) => host.feedback.show(message, type),
        refreshConversationsUI: () => host.conversationView.refresh(),
        invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => host.conversationView.invalidate(scope),
        saveChatState: (force?: boolean) => storageManager.saveState(force),
        exitSelectMode: () => controller.exitSelectMode()
    };
};

const runBatchDeleteForPage = async (host: ToolbarWiringHost, controller: ConversationToolbarController): Promise<void> => {
    const sharedDependencies = createBatchOperationSharedDependencies(host, controller);
    const selectedIds = controller.selection.list();
    await executeBatchDelete(
        {
            ...sharedDependencies,
            deleteConversations: (conversationIds) => host.conversationView.requireActions().deleteConversations(conversationIds, { confirm: false, notify: false, batchNotify: true })
        },
        selectedIds
    );
};

const runBatchCloneForPage = async (host: ToolbarWiringHost, controller: ConversationToolbarController): Promise<void> => {
    const conversationManager = host.conversationRuntime.requireConversation();
    const sharedDependencies = createBatchOperationSharedDependencies(host, controller);
    const selectedIds = controller.selection.list();
    const parseClone = (targetConversationId: string, value: WebuiConversationResponse): Conversation => {
        const cloned = parseBackendConversationRecord(value, {
            context: 'Cloned conversation',
            messagesHydrated: false
        });
        if (cloned.id !== targetConversationId) {
            throw new Error(`Cloned conversation id does not match requested conversation ${targetConversationId}`);
        }
        return cloned;
    };
    await executeBatchClone(
        {
            ...sharedDependencies,
            createConversationId: () => `conv_${generateSecureId()}`,
            cloneConversation: async (sourceConversationId, targetConversationId) => {
                const payload = await host.api.webui.chat.clone(sourceConversationId, { id: targetConversationId });
                const cloned = parseClone(targetConversationId, payload);
                conversationManager.markConversationPersisted(cloned.id);
                return cloned;
            }
        },
        selectedIds
    );
};

export { initializeConversationToolbarForPage, runBatchArchiveForPage, runBatchCloneForPage, runBatchDeleteForPage };
export type { ToolbarWiringHost };
