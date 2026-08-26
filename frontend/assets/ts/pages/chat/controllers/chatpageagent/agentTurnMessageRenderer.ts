/* SoAI - Chat page agent turn message renderer [frontend/assets/ts/pages/chat/controllers/chatpageagent/agentTurnMessageRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isArray } from '@core/typeGuards.ts';
import { buildAgentAssistantEventTimeline, buildChronologicalToolActivity, combineIterationText, getTurnStateForConversation, hasChatStreamLoadingActivityTimeline, resolveAssistantMessageTarget, resolveCollapsedOverrideMap, type ChatMessage } from '@features/chat/public.ts';
import { AgentExecutionStateController } from '@pages/chat/controllers/chatpageagent/AgentExecutionStateController.ts';
import { isPersistedAuthoritativeAssistantMessage, resolvePersistedAuthoritativeAssistantMessage } from '@pages/chat/controllers/chatpageagent/persistedAssistantTimelineController.ts';
import { patchAgentAssistantMessageDom } from '@pages/chat/controllers/chatpageagent/agentAssistantMessageDomPatchController.ts';
import { mergeSubagentActivity } from '@pages/chat/controllers/chatpageagent/subagentTimelineManager.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

interface AgentTurnMessageRendererDependencies {
    requestMessageHydration(conversationId: string, requestKey: string): void;
}

type AgentAssistantMessageResolution = { status: 'resolved'; message: ChatMessage } | { status: 'missing' };

const hasAnyToolCalls = (turnState: ReturnType<typeof getTurnStateForConversation>): boolean => {
    if (!turnState) {
        return false;
    }
    for (const iteration of turnState.iterations.values()) {
        if (isArray(iteration.toolCalls) && iteration.toolCalls.length > 0) {
            return true;
        }
    }
    return false;
};

const resolveLastAssistantMessage = (messages: ChatMessage[]): ChatMessage | null => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
        const message = messages[index];
        if (!message || message.role !== 'assistant') {
            continue;
        }
        return message;
    }
    return null;
};

const resolveAgentAssistantMessageTimestamp = (message: ChatMessage): number | null => {
    const value = message.assistantTurnAtMs ?? message.timestamp;
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
};

const buildHydrationRequestKey = (turnState: NonNullable<ReturnType<typeof getTurnStateForConversation>>): string => {
    return [turnState.turnId, String(turnState.messageIndex ?? 'latest'), String(turnState.lastSequence)].join(':');
};

const clearTerminalizedTurnState = (eventHandler: NonNullable<ChatPageAgentState['eventHandler']>, conversationId: string): void => {
    AgentExecutionStateController.clearAgentTurnStateForMarker(eventHandler, conversationId, AgentExecutionStateController.captureAgentTurnStateMarker(eventHandler, conversationId));
};

const terminalizeCurrentAgentAssistantMessage = (host: ChatPageAgentHost, conversationId: string, assistantMessage: ChatMessage): boolean => {
    if (assistantMessage.role !== 'assistant') {
        return false;
    }
    const conversation = host.conversation.getConversationById(conversationId);
    if (!conversation) {
        return false;
    }
    try {
        return patchAgentAssistantMessageDom(host, { conversation, conversationId, message: assistantMessage, mode: 'terminal' });
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('ChatPageAgent', 'Failed to terminalize current agent assistant message', runtimeError);
        host.workflow.logWarning('Failed to terminalize current agent assistant message', runtimeError);
        return false;
    }
};

const resolveExistingAssistantMessageForTurn = (messages: ChatMessage[], turnState: NonNullable<ReturnType<typeof getTurnStateForConversation>>): AgentAssistantMessageResolution => {
    if (turnState.messageIndex !== null) {
        const target = resolveAssistantMessageTarget(messages, turnState.messageIndex);
        if (target.status === 'resolved') {
            return { status: 'resolved', message: target.message };
        }
        if (target.status === 'open') {
            return { status: 'missing' };
        }
        throw new Error(target.reason);
    }
    const candidate = resolveLastAssistantMessage(messages);
    if (candidate === null) {
        return { status: 'missing' };
    }
    const timestamp = resolveAgentAssistantMessageTimestamp(candidate);
    if (timestamp !== null && timestamp >= turnState.turnStartedAtMs) {
        return { status: 'resolved', message: candidate };
    }
    return { status: 'missing' };
};

const renderAgentTurnMessage = (host: ChatPageAgentHost, state: ChatPageAgentState, dependencies: AgentTurnMessageRendererDependencies): void => {
    const eventHandler = state.eventHandler;
    if (!eventHandler) {
        return;
    }
    const conversationId = host.conversation.getCurrentConversationId();
    if (!conversationId) {
        return;
    }
    if (host.conversation.isChatStreamingConversation(conversationId)) {
        return;
    }
    const turnState = getTurnStateForConversation(eventHandler.turnStateMap, conversationId);
    if (!turnState) {
        return;
    }
    const conversation = host.conversation.getConversationById(conversationId);
    if (!conversation) {
        return;
    }
    const messages = conversation.messages;
    const persistedAuthoritativeAssistantMessage = resolvePersistedAuthoritativeAssistantMessage(conversation);
    const assistantResolution = resolveExistingAssistantMessageForTurn(messages, turnState);
    let assistantMessage = assistantResolution.status === 'resolved' ? assistantResolution.message : null;
    if (turnState.messageIndex === null && assistantMessage !== null && assistantMessage === persistedAuthoritativeAssistantMessage) {
        const timestamp = resolveAgentAssistantMessageTimestamp(assistantMessage);
        const assistantMatchesTurn = timestamp !== null && timestamp >= turnState.turnStartedAtMs;
        if (assistantMatchesTurn && turnState.status !== 'running') {
            clearTerminalizedTurnState(eventHandler, conversationId);
            return;
        }
        assistantMessage = null;
    }
    if (turnState.status !== 'running' && assistantMessage !== null && isPersistedAuthoritativeAssistantMessage(assistantMessage)) {
        clearTerminalizedTurnState(eventHandler, conversationId);
        return;
    }
    if (assistantMessage && hasChatStreamLoadingActivityTimeline(assistantMessage.assistantEventTimeline)) {
        return;
    }
    if (assistantMessage !== null && isPersistedAuthoritativeAssistantMessage(assistantMessage)) {
        return;
    }
    const orderedIterations = Array.from(turnState.iterations.entries()).sort((left, right) => left[0] - right[0]);
    const { combinedText, combinedTextCodePointCount, iterationOffsets } = combineIterationText(orderedIterations);
    if (!assistantMessage && combinedText.length === 0 && !hasAnyToolCalls(turnState)) {
        return;
    }
    if (!assistantMessage) {
        dependencies.requestMessageHydration(conversationId, buildHydrationRequestKey(turnState));
        return;
    }
    const nowMs = serverEpochMs();
    assistantMessage.content = combinedText;
    const collapsedByCallId = resolveCollapsedOverrideMap(assistantMessage.inlineToolCollapsedByCallId);
    const nextToolActivity = mergeSubagentActivity(buildChronologicalToolActivity(orderedIterations, iterationOffsets, collapsedByCallId), turnState.subagents, collapsedByCallId, iterationOffsets, combinedTextCodePointCount, conversationId);
    assistantMessage.assistantEventTimeline = buildAgentAssistantEventTimeline(assistantMessage.timestamp ?? nowMs, combinedText, nextToolActivity);
    if (turnState.status !== 'running' && terminalizeCurrentAgentAssistantMessage(host, conversationId, assistantMessage)) {
        return;
    }
    if (host.conversation.getCurrentConversationId() === conversationId) {
        host.rendering.messages.invalidateMessageCache(assistantMessage);
        if (patchAgentAssistantMessageDom(host, { conversation, conversationId, message: assistantMessage, mode: 'running' })) {
            return;
        }
    }
    host.rendering.scheduleConversationRender().catch((error) => {
        const narrowed = ensureError(error);
        host.workflow.logWarning('Failed to rerender conversation after agent turn update', narrowed);
    });
};

export { renderAgentTurnMessage };
