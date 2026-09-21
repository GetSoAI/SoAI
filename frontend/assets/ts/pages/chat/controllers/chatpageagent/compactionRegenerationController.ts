/* SoAI - Chat page compaction regeneration controller [frontend/assets/ts/pages/chat/controllers/chatpageagent/compactionRegenerationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import type { AgentCheckpointResponse } from '@core/api/contracts/chatAgentContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { isNumber } from '@core/typeGuards.ts';
import { isChatMessage, isCompactionConflictError, rehydrateTurnStateFromCheckpoint, type ChatMessage } from '@features/chat/public.ts';
import { patchAgentAssistantMessageDom } from '@pages/chat/controllers/chatpageagent/agentAssistantMessageDomPatchController.ts';
import { ensureCompactionModelSettings } from '@pages/chat/controllers/chatpageagent/compactionModelSettingsManager.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

const findCompactionTarget = (host: ChatPageAgentHost, conversationId: string, assistantTurnAtMs: number): ChatMessage | null => {
    const conversation = host.conversation.getConversationById(conversationId);
    if (!conversation) return null;
    return (
        conversation.messages.find((message) => {
            if (!isChatMessage(message) || message.role !== 'assistant') return false;
            const turnTimestamp = message.assistantTurnAtMs;
            const timestamp = message.timestamp;
            return (isNumber(turnTimestamp) && Number.isInteger(turnTimestamp) && turnTimestamp === assistantTurnAtMs) || (isNumber(timestamp) && Number.isInteger(timestamp) && timestamp === assistantTurnAtMs);
        }) ?? null
    );
};

const patchCompactionTarget = (host: ChatPageAgentHost, conversationId: string, assistantTurnAtMs: number): void => {
    const conversation = host.conversation.getConversationById(conversationId);
    const message = findCompactionTarget(host, conversationId, assistantTurnAtMs);
    if (!conversation || !message) {
        throw new Error('Agent compaction regeneration response omitted the target assistant message');
    }
    const messageHost = host.rendering.messages;
    messageHost.invalidateMessageCache(message);
    if (!patchAgentAssistantMessageDom(host, { conversation, conversationId, message, mode: 'compactionRefresh' })) {
        throw new Error('Agent compaction regeneration requires the target assistant message root');
    }
};

const handleAgentCompactionRegeneration = async (host: ChatPageAgentHost, state: ChatPageAgentState, assistantTurnAtMs: number, dependencies: { isDisposed: () => boolean; initialize: () => void; renderAgentTurnMessage: () => void; updateUiForCurrentConversation: () => void }): Promise<void> => {
    try {
        await host.workflow.runWithBoundary('chat:agentRegenerateCompaction', async () => {
            dependencies.initialize();
            if (dependencies.isDisposed()) return;
            const conversation = host.conversation.getCurrentConversation();
            if (!conversation?.id) throw new Error('Agent compaction regeneration requires a conversation id');
            const conversationId = conversation.id;
            if (!findCompactionTarget(host, conversationId, assistantTurnAtMs)) {
                throw new Error('Agent compaction regeneration requires the target assistant message in the active conversation');
            }
            if (host.conversation.isConversationExecuting(conversationId)) {
                throw new Error('Agent compaction regeneration requires an idle conversation');
            }
            const activation = host.conversation.captureConversationActivationSnapshot();
            await ensureCompactionModelSettings(host, conversation);
            if (dependencies.isDisposed()) throw new Error('Agent compaction regeneration cancelled because the chat page was disposed');
            if (!host.conversation.isConversationActivationSnapshotCurrent(activation, conversationId) || !findCompactionTarget(host, conversationId, assistantTurnAtMs)) return;
            const expectedRevision = conversation.updatedAt;
            if (!Number.isInteger(expectedRevision) || Number(expectedRevision) <= 0) {
                throw new Error('Agent compaction regeneration requires a conversation revision');
            }
            if (!state.eventHandler) throw new Error('Agent event handler is not initialized');
            const request = {
                assistantTurnAtMs,
                clientId: windowIdentity.current(),
                clientRequestId: generateSecureId({ prefix: 'compact_regenerate_req', separator: '_' }),
                expectedLastModifiedAtMs: Number(expectedRevision)
            };
            let checkpointPayload: AgentCheckpointResponse;
            try {
                checkpointPayload = await host.conversation.getApi().webui.chat.agent.regenerateCompaction(conversationId, request);
            } catch (error) {
                if (!isNetworkError(error) && !isRequestTimeoutError(error)) throw error;
                checkpointPayload = await host.conversation.getApi().webui.chat.agent.regenerateCompaction(conversationId, request);
            }
            if (dependencies.isDisposed()) return;
            if (!host.conversation.isConversationActivationSnapshotCurrent(activation, conversationId)) return;
            if (!rehydrateTurnStateFromCheckpoint(state.eventHandler.turnStateMap, checkpointPayload)) {
                state.eventHandler.clearConversationTurnState(conversationId);
                throw new Error('Agent compaction regeneration returned a stale checkpoint payload');
            }
            await host.conversation.loadConversationMessages(conversationId, { force: true });
            patchCompactionTarget(host, conversationId, assistantTurnAtMs);
            dependencies.renderAgentTurnMessage();
            dependencies.updateUiForCurrentConversation();
        });
    } catch (error) {
        if (dependencies.isDisposed()) return;
        const runtimeError = ensureError(error);
        const message = isCompactionConflictError(runtimeError) ? i18n.t('chat.agent.compact.conflict') : i18n.t('chat.agent.compact.failed');
        host.workflow.feedback.show(message, isCompactionConflictError(runtimeError) ? 'warning' : 'error');
    }
};

export { handleAgentCompactionRegeneration };
