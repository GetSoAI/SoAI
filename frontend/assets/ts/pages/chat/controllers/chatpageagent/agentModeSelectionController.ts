/* SoAI - Agent mode selection persistence flow for the chat page [frontend/assets/ts/pages/chat/controllers/chatpageagent/agentModeSelectionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';
import { ensureError, extractApiErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { selectAndPersistAgentMode } from '@features/chat/public.ts';
import { resolveEffectiveConversationModel } from '@pages/chat/controllers/chatpageagent/compactionModelSettingsManager.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

interface AgentModeSelectionRuntimeDependencies {
    isDisposed(): boolean;
    initialize(): void;
    updateUiForCurrentConversation(): void;
    showModePopup(mode: AgentMode): void;
}

const handleAgentModeSelection = (host: ChatPageAgentHost, state: ChatPageAgentState, dependencies: AgentModeSelectionRuntimeDependencies, targetMode: AgentMode | null): void => {
    if (dependencies.isDisposed()) {
        return;
    }
    if (state.pendingModeUpdate) {
        dependencies.updateUiForCurrentConversation();
        return;
    }
    const run = async (): Promise<void> => {
        dependencies.initialize();
        if (dependencies.isDisposed()) {
            return;
        }
        await selectAndPersistAgentMode(
            {
                getCurrentConversation: () => host.conversation.getCurrentConversation(),
                updateConversationSettings: async (conversationId, patch) => {
                    if (dependencies.isDisposed()) {
                        throw new Error('Agent mode update cancelled because the chat page was disposed');
                    }
                    const conversationManager = host.conversation.manager;
                    const conversation = host.conversation.getConversationById(conversationId);
                    if (!conversation) {
                        throw new Error(`Conversation not found for agent mode update: ${conversationId}`);
                    }
                    const previousModelSettings = conversation.modelSettings;
                    const modelId = resolveEffectiveConversationModel(host, conversation);
                    try {
                        await conversationManager.ensureConversationPersisted(conversation);
                        if (dependencies.isDisposed()) {
                            throw new Error('Agent mode update cancelled because the chat page was disposed');
                        }
                        await conversationManager.updateConversationSettings(conversationId, modelId ? { ...patch, model: modelId } : patch);
                    } catch (error) {
                        conversation.modelSettings = previousModelSettings;
                        throw error;
                    }
                },
                onModeChanged: (conversationId, mode) => {
                    if (dependencies.isDisposed()) {
                        return;
                    }
                    host.interaction.syncToolsEnabledParameterFromConversation(conversationId);
                    host.interaction.handleCurrentConversationToolsLockStateChange();
                    dependencies.updateUiForCurrentConversation();
                    host.interaction.updateInputState();
                    host.interaction.updateParameterUI();
                    const currentConversation = host.conversation.getCurrentConversation();
                    if (!currentConversation || currentConversation.id !== conversationId) {
                        return;
                    }
                    dependencies.showModePopup(mode);
                }
            },
            targetMode
        );
        if (dependencies.isDisposed()) {
            return;
        }
        dependencies.updateUiForCurrentConversation();
        host.interaction.refreshTokenCounterPreview();
    };
    const modeUpdatePromise = host.workflow
        .runWithBoundary('chat:agentModeSelection', run)
        .catch((error) => {
            if (dependencies.isDisposed()) {
                return;
            }
            const narrowed = ensureError(error);
            host.workflow.logWarning('Failed to update agent mode', narrowed);
            host.workflow.feedback.show(extractApiErrorMessage(error) ?? i18n.t('chat.agent.mode.updateFailed'), 'error');
        })
        .finally(() => {
            if (state.pendingModeUpdate === modeUpdatePromise) {
                state.pendingModeUpdate = null;
            }
        });
    state.pendingModeUpdate = modeUpdatePromise;
};

export { handleAgentModeSelection };
