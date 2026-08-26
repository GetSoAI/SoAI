/* SoAI - Chat page operations [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/operations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { CHAT_SIDEBAR_OVERLAY_BREAKPOINT_PX } from '@pages/chat/contracts/constants.ts';
import { resolveHydratedConversationParameters } from '@pages/chat/controllers/chatconversationactionscontroller/conversationRuntimeSettingsState.ts';
import type { ChatConversationSettingsManager, ChatStreamingController, ConversationActionsHost, ConversationActionsStateAccess, ConversationManager, StorageManager, UiManager } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';
import type { ConversationDeleteOperationOptions, ConversationOperationOptions } from '@pages/chat/controllers/chatconversationactionscontroller/contracts.ts';

interface ConversationOperationsDependencies {
    host: ConversationActionsHost;
    state: ConversationActionsStateAccess;
    conversationManager: ConversationManager;
    storageManager: StorageManager;
    uiManager: UiManager;
    chatStreamingController: ChatStreamingController;
    getConversationSettingsManager(): ChatConversationSettingsManager | null;
}

const refreshConversationModelUi = (dependencies: ConversationOperationsDependencies): void => {
    dependencies.host.view.updateModelUI();
    dependencies.host.view.refreshParameterUI();
};

const applyStoredConversationModel = (dependencies: ConversationOperationsDependencies, storedModelKey: string | null): void => {
    if (!storedModelKey) {
        return;
    }
    if (!dependencies.state.hasModels()) {
        dependencies.state.setCurrentModel(storedModelKey);
        return;
    }
    dependencies.state.setCurrentModel(dependencies.state.resolveModelKey(storedModelKey) ?? storedModelKey);
};

const applyConversationSettingsAuthorityRefresh = async (dependencies: ConversationOperationsDependencies, conversationId: string): Promise<void> => {
    if (dependencies.state.getCurrentConversationId() !== conversationId) {
        return;
    }
    const conversation = dependencies.host.view.getCurrentConversation();
    if (!conversation || conversation.id !== conversationId) {
        return;
    }
    applyStoredConversationModel(dependencies, conversation.modelSettings.model);
    dependencies.state.setParameters(resolveHydratedConversationParameters(dependencies.state.getParameters(), conversation));
    refreshConversationModelUi(dependencies);
    dependencies.uiManager.applyExecutionControls();
    dependencies.host.view.applyInputActionVisibility();
    dependencies.host.view.refreshTokenCounterPreview();
    dependencies.host.view.invalidateChatMarkup('current');
    await dependencies.host.view.refreshConversationsUI();
};

const commitConversationSwitchOperation = (dependencies: ConversationOperationsDependencies, conversationId: string): void => {
    dependencies.uiManager.rememberCurrentConversationScrollPosition();
    const { storedModelKey } = dependencies.conversationManager.switchConversation(conversationId);
    dependencies.getConversationSettingsManager()?.handleConversationSwitch?.(conversationId);
    dependencies.storageManager.saveChatState();
    applyStoredConversationModel(dependencies, storedModelKey ?? null);
    const switchedConversation = dependencies.state.getCurrentConversationId() === conversationId ? dependencies.host.view.getCurrentConversation() : null;
    dependencies.state.setParameters(resolveHydratedConversationParameters(dependencies.state.getParameters(), switchedConversation));
    refreshConversationModelUi(dependencies);
    dependencies.uiManager.applyExecutionControls();
    dependencies.host.view.applyInputActionVisibility();
    const shouldRestoreScrollPosition = dependencies.uiManager.prepareConversationScrollRestore(conversationId);
    dependencies.uiManager.setAutoScrollEnabled(!shouldRestoreScrollPosition);
};

const commitConversationClearOperation = (dependencies: ConversationOperationsDependencies): void => {
    dependencies.getConversationSettingsManager()?.handleConversationSwitch?.(null);
    dependencies.uiManager.rememberCurrentConversationScrollPosition();
    dependencies.state.setCurrentConversationId(null);
    dependencies.state.setSelectedConversationHydrationState({
        conversationId: null,
        status: 'idle'
    });
    dependencies.storageManager.saveChatState();
    refreshConversationModelUi(dependencies);
    dependencies.uiManager.applyExecutionControls();
    dependencies.host.view.applyInputActionVisibility();
};

const applyConversationColorUpdateOperation = async (dependencies: ConversationOperationsDependencies, conversationId: string, color: string | null): Promise<void> => {
    await dependencies.conversationManager.updateConversationColor(conversationId, color);
    dependencies.storageManager.saveChatState();
    await dependencies.host.view.refreshConversationListAndHeader();
};

const applyConversationFavoriteToggleOperation = async (dependencies: ConversationOperationsDependencies, conversationId: string): Promise<void> => {
    await dependencies.conversationManager.toggleConversationFavorite(conversationId);
    dependencies.storageManager.saveChatState(true);
    await dependencies.host.view.refreshConversationListAndHeader();
};

const applyConversationArchiveOperation = async (dependencies: ConversationOperationsDependencies, conversationId: string): Promise<void> => {
    await dependencies.conversationManager.setArchived(conversationId, true);
    dependencies.storageManager.saveChatState(true);
    await dependencies.host.view.refreshConversationsUI();
};

const isArchiveLimitError = (error: Error): boolean => {
    return error instanceof APIError && error.code === 'archive_limit_reached';
};

const collapseSidebarIfNarrowViewport = (dependencies: ConversationOperationsDependencies): void => {
    if (dependencies.state.getSidebarOpen() && dependencies.state.getViewportWidth() <= CHAT_SIDEBAR_OVERLAY_BREAKPOINT_PX) {
        dependencies.state.setSidebarOpen(false);
        dependencies.host.view.applySidebarState();
        dependencies.storageManager.saveChatState();
    }
};

export { applyConversationArchiveOperation, applyConversationColorUpdateOperation, applyConversationFavoriteToggleOperation, applyConversationSettingsAuthorityRefresh, collapseSidebarIfNarrowViewport, commitConversationClearOperation, commitConversationSwitchOperation, isArchiveLimitError };
export type { ConversationDeleteOperationOptions };
export type { ConversationOperationOptions, ConversationOperationsDependencies };
