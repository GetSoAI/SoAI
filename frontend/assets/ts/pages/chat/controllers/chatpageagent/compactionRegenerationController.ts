/* SoAI - Chat page compaction regeneration controller [frontend/assets/ts/pages/chat/controllers/chatpageagent/compactionRegenerationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { isArray, isNumber, isObject } from '@core/typeGuards.ts';
import { isChatMessage, isCompactionConflictError, rehydrateTurnStateFromCheckpoint, type AssistantEventTimelineItem, type ChatMessage, type SoaiCompactionMarker } from '@features/chat/public.ts';
import { patchAgentAssistantMessageDom } from '@pages/chat/controllers/chatpageagent/agentAssistantMessageDomPatchController.ts';
import { ensureCompactionModelSettings } from '@pages/chat/controllers/chatpageagent/compactionModelSettingsManager.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

type RegenerationRestoreState = {
    conversationId: string;
    assistantTurnAtMs: number;
    message: ChatMessage;
    content: string;
    timeline: AssistantEventTimelineItem[];
    compactionMarker: SoaiCompactionMarker | null;
};

const readCompactionMarker = (value: SoaiCompactionMarker | null | undefined): SoaiCompactionMarker | null => value ?? null;

const isTargetAssistantTurn = (message: ChatMessage, assistantTurnAtMs: number): boolean => {
    const assistantTurnValue = message.assistantTurnAtMs;
    if (isNumber(assistantTurnValue) && Number.isInteger(assistantTurnValue) && assistantTurnValue === assistantTurnAtMs) {
        return true;
    }
    const timestampValue = message.timestamp;
    return isNumber(timestampValue) && Number.isInteger(timestampValue) && timestampValue === assistantTurnAtMs;
};

const captureAndClearAssistantMessage = (host: ChatPageAgentHost, conversationId: string, assistantTurnAtMs: number): RegenerationRestoreState | null => {
    const conversation = host.conversation.getConversationById(conversationId);
    if (!conversation) {
        return null;
    }
    const messages = isArray(conversation.messages) ? conversation.messages : null;
    if (!messages) {
        return null;
    }
    for (const message of messages) {
        if (!isChatMessage(message) || message.role !== 'assistant') {
            continue;
        }
        if (!isTargetAssistantTurn(message, assistantTurnAtMs)) {
            continue;
        }
        const previousContent = typeof message.content === 'string' ? message.content : '';
        const previousTimeline = [...(message.assistantEventTimeline ?? [])];
        const previousCompactionMarker = readCompactionMarker(message.soaiCompaction ?? null);
        message.content = '';
        message.assistantEventTimeline = [];
        delete message.soaiCompaction;
        return {
            conversationId,
            assistantTurnAtMs,
            message,
            content: previousContent,
            timeline: previousTimeline,
            compactionMarker: previousCompactionMarker
        };
    }
    return null;
};

const patchCurrentAssistantMessageRoot = (host: ChatPageAgentHost, conversationId: string, message: ChatMessage): void => {
    if (host.conversation.getCurrentConversationId() !== conversationId) {
        return;
    }
    const conversation = host.conversation.getConversationById(conversationId);
    if (!conversation || !isArray(conversation.messages)) {
        throw new Error('Agent compaction regeneration patch requires the active conversation');
    }
    if (!isChatMessage(message) || message.role !== 'assistant') {
        throw new Error('Agent compaction regeneration patch requires an assistant message');
    }
    const messageHost = host.rendering.messages;
    messageHost.invalidateMessageCache(message);
    if (!patchAgentAssistantMessageDom(host, { conversation, conversationId, message, mode: 'compactionRefresh' })) {
        throw new Error('Agent compaction regeneration patch requires the assistant message root');
    }
};

const isStillClearedCompactionMessage = (message: ChatMessage): boolean => {
    if (message.content !== '') {
        return false;
    }
    if (isArray(message.assistantEventTimeline) && message.assistantEventTimeline.length > 0) {
        return false;
    }
    return readCompactionMarker(message.soaiCompaction ?? null) === null;
};

const tryRestoreClearedAssistantMessage = (host: ChatPageAgentHost, restoreState: RegenerationRestoreState, shouldPatchDom: boolean): void => {
    const conv = host.conversation.getConversationById(restoreState.conversationId);
    if (!conv || !isArray(conv.messages)) {
        return;
    }
    for (const message of conv.messages) {
        if (message !== restoreState.message || !isObject(message) || isArray(message)) {
            continue;
        }
        if (!isChatMessage(message) || !isTargetAssistantTurn(message, restoreState.assistantTurnAtMs)) {
            continue;
        }
        if (!isStillClearedCompactionMessage(message)) {
            return;
        }
        message['content'] = restoreState.content;
        message.assistantEventTimeline = restoreState.timeline;
        if (restoreState.compactionMarker === null) {
            delete message.soaiCompaction;
        } else {
            message.soaiCompaction = restoreState.compactionMarker;
        }
        if (shouldPatchDom) {
            try {
                patchCurrentAssistantMessageRoot(host, restoreState.conversationId, restoreState.message);
            } catch (restoreError) {
                const runtimeError = ensureError(restoreError);
                errorHandler.warn('ChatPageAgent', 'Failed to patch restored compaction boundary message', runtimeError);
                host.workflow.logWarning('Failed to patch restored compaction boundary message', runtimeError);
            }
        }
        return;
    }
};

const handleAgentCompactionRegeneration = async (host: ChatPageAgentHost, state: ChatPageAgentState, assistantTurnAtMs: number, dependencies: { isDisposed: () => boolean; initialize: () => void; renderAgentTurnMessage: () => void; updateUiForCurrentConversation: () => void }): Promise<void> => {
    const restoreStateRef: { value: RegenerationRestoreState | null } = { value: null };
    try {
        await host.workflow.runWithBoundary('chat:agentRegenerateCompaction', async () => {
            dependencies.initialize();
            if (dependencies.isDisposed()) {
                return;
            }
            const conversation = host.conversation.getCurrentConversation();
            if (!conversation) {
                return;
            }
            if (!conversation.id) {
                throw new Error('Agent compaction regeneration requires a conversation id');
            }
            const conversationId = conversation.id;
            if (host.conversation.isConversationExecuting(conversationId)) {
                throw new Error('Agent compaction regeneration requires an idle conversation');
            }
            const activation = host.conversation.captureConversationActivationSnapshot();

            const restoreState = captureAndClearAssistantMessage(host, conversationId, assistantTurnAtMs);
            if (restoreState === null) {
                throw new Error('Agent compaction regeneration requires the target assistant message in the active conversation');
            }
            restoreStateRef.value = restoreState;
            patchCurrentAssistantMessageRoot(host, restoreState.conversationId, restoreState.message);

            await ensureCompactionModelSettings(host, conversation);
            if (dependencies.isDisposed()) {
                throw new Error('Agent compaction regeneration cancelled because the chat page was disposed');
            }
            if (!state.eventHandler) {
                throw new Error('Agent event handler is not initialized');
            }
            const checkpointPayload = await host.conversation.getApi().webui.chat.agent.regenerateCompaction(conversationId, {
                assistantTurnAtMs: assistantTurnAtMs
            });
            if (dependencies.isDisposed()) {
                throw new Error('Agent compaction regeneration cancelled because the chat page was disposed');
            }
            if (!host.conversation.isConversationActivationSnapshotCurrent(activation, conversationId)) {
                throw new Error('Agent compaction regeneration became stale after conversation switch');
            }
            const checkpoint = checkpointPayload;
            if (!rehydrateTurnStateFromCheckpoint(state.eventHandler.turnStateMap, checkpoint)) {
                state.eventHandler.clearConversationTurnState(conversationId);
                throw new Error('Agent compaction regeneration returned a stale checkpoint payload');
            }
            restoreStateRef.value = null;
            dependencies.renderAgentTurnMessage();
            dependencies.updateUiForCurrentConversation();
        });
    } catch (error) {
        const runtimeError = ensureError(error);
        const resolvedRestoreState = restoreStateRef.value;
        const shouldPatchRestoredMessage = !dependencies.isDisposed();
        if (resolvedRestoreState !== null) {
            tryRestoreClearedAssistantMessage(host, resolvedRestoreState, shouldPatchRestoredMessage);
        }
        if (!shouldPatchRestoredMessage) {
            return;
        }
        const message = isCompactionConflictError(runtimeError) ? i18n.t('chat.agent.compact.conflict') : i18n.t('chat.agent.compact.failed');
        if (isCompactionConflictError(runtimeError)) {
            host.workflow.feedback.show(message, 'warning');
            return;
        }
        host.workflow.feedback.show(message, 'error');
    }
};

export { handleAgentCompactionRegeneration };
