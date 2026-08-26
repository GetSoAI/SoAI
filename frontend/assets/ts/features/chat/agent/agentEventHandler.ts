/* SoAI - Chat feature agent event handler [frontend/assets/ts/features/chat/agent/agentEventHandler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyAgentParentTurnEvent, applyAgentTurnEvent, isCurrentAgentEventConversation, resolveMatchingTurnState } from '@features/chat/agent/agentEventTurnGate.ts';
import { applySubagentEvent } from '@features/chat/agent/agentSubagentStateManager.ts';
import { applyItemCompleted, applyItemDelta, applyItemStarted } from '@features/chat/agent/agentIterationStateManager.ts';
import { applyToolCallCompleted, applyToolCallCreated, applyToolCallRunning, applyToolCallStarted } from '@features/chat/agent/agentIterationToolCallStateManager.ts';
import { applyTodoUpdated, applyTurnCompleted, applyTurnError, createAgentTurnStateMap, getOrCreateTurnState, type AgentTurnStateMap } from '@features/chat/agent/agentTurnStateManager.ts';
import { subscribeToAgentEvents } from '@features/chat/agent/agentEventSubscriptions.ts';
import type { WebSocketEventBatchSubscribe } from '@core/realtime/websocketBatchSubscription.ts';
import type { AgentMode } from '@core/chat/agentMode.ts';
import type { AgentPlanStep } from '@core/chat/agentTypes.ts';

interface AgentEventHandlerCallbacks {
    getCurrentConversationId(): string | null;
    onIterationRenderNeeded(convId: string, iterationIndex: number): void;
    onToolCallRenderNeeded(convId: string, iterationIndex: number): void;
    onToolCallDurationUpdated(convId: string, toolCallId: string, toolName: string, startedAtMs: number, durationMs: number): void;
    onTurnRunningStateChanged(convId: string): void;
    onTurnCompleted(convId: string): void;
    onTurnError(convId: string, message: string): void;
    onTodoUpdated(convId: string, todo: AgentPlanStep[], explanation: string | null, revision: number): void;
    onPlanUpdated(convId: string, title: string | null, markdown: string, revision: number): void;
    onModeChanged(convId: string, mode: AgentMode): void;
    onSubagentRenderNeeded(convId: string): void;
    getNowMs(): number;
}

interface AgentEventHandlerResult {
    turnStateMap: AgentTurnStateMap;
    clearConversationTurnState(convId: string): boolean;
    dispose(): void;
}

const createAgentEventHandler = (callbacks: AgentEventHandlerCallbacks, subscribe?: WebSocketEventBatchSubscribe): AgentEventHandlerResult => {
    const turnStateMap = createAgentTurnStateMap();

    const unsubscribers = subscribeToAgentEvents(
        {
            onTurnStarted(payload): void {
                getOrCreateTurnState(turnStateMap, payload.convId, payload.turnId, payload.mode, payload.maxIterations, callbacks.getNowMs());
                callbacks.onTurnRunningStateChanged(payload.convId);
                if (isCurrentAgentEventConversation(callbacks, payload.convId)) {
                    callbacks.onIterationRenderNeeded(payload.convId, payload.iterationIndex);
                }
            },

            onItemStarted(payload): void {
                applyAgentTurnEvent({
                    turnStateMap,
                    payload,
                    scope: callbacks,
                    apply: (turnState) => applyItemStarted(turnState, payload.iterationIndex, payload.itemId, payload.itemType, payload.sequence),
                    render: (convId) => callbacks.onIterationRenderNeeded(convId, payload.iterationIndex)
                });
            },

            onItemDelta(payload): void {
                applyAgentTurnEvent({
                    turnStateMap,
                    payload,
                    scope: callbacks,
                    apply: (turnState) => applyItemDelta(turnState, payload.iterationIndex, payload.textDelta, payload.sequence),
                    render: (convId) => callbacks.onIterationRenderNeeded(convId, payload.iterationIndex)
                });
            },

            onItemCompleted(payload): void {
                applyAgentTurnEvent({
                    turnStateMap,
                    payload,
                    scope: callbacks,
                    apply: (turnState) => applyItemCompleted(turnState, payload.iterationIndex, payload.itemId, payload.finalText, payload.sequence),
                    render: (convId) => callbacks.onIterationRenderNeeded(convId, payload.iterationIndex)
                });
            },

            onToolCallCreated(payload): void {
                applyAgentTurnEvent({
                    turnStateMap,
                    payload,
                    scope: callbacks,
                    apply: (turnState) => applyToolCallCreated(turnState, payload.iterationIndex, payload.messageIndex, payload.toolCallId, payload.toolName, payload.toolArguments, payload.sequence),
                    render: (convId) => callbacks.onToolCallRenderNeeded(convId, payload.iterationIndex)
                });
            },

            onToolCallStarted(payload): void {
                applyAgentTurnEvent({
                    turnStateMap,
                    payload,
                    scope: callbacks,
                    apply: (turnState) => applyToolCallStarted(turnState, payload.iterationIndex, payload.messageIndex, payload.toolCallId, payload.toolName, payload.toolArguments, payload.sequence, payload.startedAtMs),
                    render: (convId) => callbacks.onToolCallRenderNeeded(convId, payload.iterationIndex)
                });
            },

            onToolCallCompleted(payload): void {
                applyAgentTurnEvent({
                    turnStateMap,
                    payload,
                    scope: callbacks,
                    apply: (turnState) => applyToolCallCompleted(turnState, payload.iterationIndex, payload.messageIndex, payload.toolCallId, payload.toolName, payload.toolArguments, payload.result, payload.codeDiffs, payload.sequence, payload.status, payload.startedAtMs, payload.durationMs),
                    render: (convId) => callbacks.onToolCallRenderNeeded(convId, payload.iterationIndex)
                });
            },

            onToolCallRunning(payload): void {
                applyAgentTurnEvent({
                    turnStateMap,
                    payload,
                    scope: callbacks,
                    apply: (turnState) => applyToolCallRunning(turnState, payload.iterationIndex, payload.toolCallId, payload.sequence, payload.startedAtMs, payload.durationMs),
                    render: (convId) => callbacks.onToolCallDurationUpdated(convId, payload.toolCallId, payload.toolName, payload.startedAtMs, payload.durationMs)
                });
            },

            onTurnCompleted(payload): void {
                const turnState = resolveMatchingTurnState(turnStateMap, payload);
                if (!turnState) {
                    return;
                }
                if (!applyTurnCompleted(turnState, payload.sequence)) {
                    return;
                }
                callbacks.onTurnRunningStateChanged(payload.convId);
                if (isCurrentAgentEventConversation(callbacks, payload.convId)) {
                    callbacks.onTurnCompleted(payload.convId);
                }
            },

            onTurnError(payload): void {
                const turnState = resolveMatchingTurnState(turnStateMap, payload);
                if (!turnState) {
                    return;
                }
                if (!applyTurnError(turnState, payload.sequence)) {
                    return;
                }
                callbacks.onTurnRunningStateChanged(payload.convId);
                if (isCurrentAgentEventConversation(callbacks, payload.convId)) {
                    callbacks.onTurnError(payload.convId, payload.message);
                }
            },

            onTodoUpdated(payload): void {
                const turnState = resolveMatchingTurnState(turnStateMap, payload);
                if (turnState) {
                    const applied = applyTodoUpdated(turnState, payload.todo, payload.explanation, payload.sequence);
                    if (isCurrentAgentEventConversation(callbacks, payload.convId)) {
                        if (applied) {
                            callbacks.onTodoUpdated(payload.convId, turnState.todo, turnState.todoExplanation, payload.revision);
                        } else {
                            callbacks.onTodoUpdated(payload.convId, payload.todo, payload.explanation, payload.revision);
                        }
                    }
                    return;
                }
                if (isCurrentAgentEventConversation(callbacks, payload.convId)) {
                    callbacks.onTodoUpdated(payload.convId, payload.todo, payload.explanation, payload.revision);
                }
            },

            onPlanUpdated(payload): void {
                if (isCurrentAgentEventConversation(callbacks, payload.convId)) {
                    callbacks.onPlanUpdated(payload.convId, payload.title, payload.markdown, payload.revision);
                }
            },

            onModeChanged(payload): void {
                if (isCurrentAgentEventConversation(callbacks, payload.convId)) {
                    callbacks.onModeChanged(payload.convId, payload.mode);
                }
            },

            onSubagentUpdated(payload): void {
                applyAgentParentTurnEvent({
                    turnStateMap,
                    payload,
                    scope: callbacks,
                    apply: (turnState) => applySubagentEvent(turnState, payload),
                    render: (convId) => callbacks.onSubagentRenderNeeded(convId)
                });
            }
        },
        subscribe
    );

    const dispose = (): void => {
        for (const unsubscribe of unsubscribers) {
            unsubscribe();
        }
        turnStateMap.clear();
    };

    const clearConversationTurnState = (convId: string): boolean => {
        return turnStateMap.delete(convId);
    };

    return { turnStateMap, clearConversationTurnState, dispose };
};

export { createAgentEventHandler };
export type { AgentEventHandlerCallbacks, AgentEventHandlerResult };
