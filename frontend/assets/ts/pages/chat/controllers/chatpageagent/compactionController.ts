/* SoAI - Chat page compaction controller [frontend/assets/ts/pages/chat/controllers/chatpageagent/compactionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { ensureManualCompactionAssistantPlaceholder, isCompactionConflictError, rehydrateTurnStateFromCheckpoint, startManualCompaction } from '@features/chat/public.ts';
import { isConversationAuthorityLocked } from '@core/chat/conversationAuthorityLock.ts';
import { ensureCompactionModelSettings } from '@pages/chat/controllers/chatpageagent/compactionModelSettingsManager.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import { setManualCompactionStartingState, updateAgentCompactButton } from '@pages/chat/controllers/chatpageagent/effects.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

const executeCompaction = (host: ChatPageAgentHost, state: ChatPageAgentState, renderAgentTurnMessage: () => void, updateUiForCurrentConversation: () => void): void => {
    const run = async (): Promise<void> => {
        const conversation = host.conversation.getCurrentConversation();
        if (!conversation) {
            return;
        }
        const conversationId = conversation.id;
        const activation = host.conversation.captureConversationActivationSnapshot();
        const modelId = await ensureCompactionModelSettings(host, conversation);
        const conversationManager = host.conversation.manager;
        await conversationManager.ensureConversationPersisted(conversation);

        const startCheckpoint = await startManualCompaction(host.conversation.getApi(), conversationId, modelId);
        if (!host.conversation.isConversationActivationSnapshotCurrent(activation, conversationId)) {
            return;
        }
        if (!state.eventHandler) {
            throw new Error('Manual compaction start checkpoint is invalid.');
        }
        const rehydrated = rehydrateTurnStateFromCheckpoint(state.eventHandler.turnStateMap, startCheckpoint);
        if (!rehydrated) {
            state.eventHandler.clearConversationTurnState(conversationId);
            throw new Error('Manual compaction start checkpoint is stale.');
        }
        ensureManualCompactionAssistantPlaceholder(conversation, startCheckpoint);
        renderAgentTurnMessage();
        updateUiForCurrentConversation();
        await host.conversation.refreshConversationsUI();
        updateAgentCompactButton(host, state, host.conversation.getCurrentConversation());
    };
    const conversationId = host.conversation.getCurrentConversationId();
    if (!conversationId) {
        return;
    }
    if (isConversationAuthorityLocked(host.conversation.getCurrentConversation())) {
        return;
    }
    setManualCompactionStartingState(host, state, conversationId, true);
    updateAgentCompactButton(host, state, host.conversation.getCurrentConversation());
    host.workflow
        .runWithBoundary('chat:agentCompact', run)
        .catch((error) => {
            if (isCompactionConflictError(error)) {
                host.workflow.feedback.show(i18n.t('chat.agent.compact.conflict'), 'warning');
                return;
            }
            host.workflow.feedback.show(i18n.t('chat.agent.compact.failed'), 'error');
        })
        .finally(() => {
            setManualCompactionStartingState(host, state, conversationId, false);
            updateAgentCompactButton(host, state, host.conversation.getCurrentConversation());
        });
};

export { executeCompaction };
