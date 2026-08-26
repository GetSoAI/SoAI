/* SoAI - Chat feature agent event subscriptions [frontend/assets/ts/features/chat/agent/agentEventSubscriptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts, type WebSocketEventBatchSubscribe } from '@core/realtime/websocketBatchSubscription.ts';
import type { AgentSubagentEventPayload } from '@core/chat/agentSubagentTypes.ts';
import type { AgentItemCompletedPayload, AgentItemDeltaPayload, AgentItemStartedPayload, AgentModeChangedPayload, AgentPlanUpdatedPayload, AgentTodoUpdatedPayload, AgentToolCallCompletedPayload, AgentToolCallCreatedPayload, AgentToolCallRunningPayload, AgentToolCallStartedPayload, AgentTurnCompletedPayload, AgentTurnErrorPayload, AgentTurnStartedPayload } from '@core/chat/agentTypes.ts';

interface AgentEventListener {
    onTurnStarted(payload: AgentTurnStartedPayload): void;
    onItemStarted(payload: AgentItemStartedPayload): void;
    onItemDelta(payload: AgentItemDeltaPayload): void;
    onItemCompleted(payload: AgentItemCompletedPayload): void;
    onToolCallCreated(payload: AgentToolCallCreatedPayload): void;
    onToolCallStarted(payload: AgentToolCallStartedPayload): void;
    onToolCallRunning(payload: AgentToolCallRunningPayload): void;
    onToolCallCompleted(payload: AgentToolCallCompletedPayload): void;
    onTurnCompleted(payload: AgentTurnCompletedPayload): void;
    onTurnError(payload: AgentTurnErrorPayload): void;
    onTodoUpdated(payload: AgentTodoUpdatedPayload): void;
    onPlanUpdated(payload: AgentPlanUpdatedPayload): void;
    onModeChanged(payload: AgentModeChangedPayload): void;
    onSubagentUpdated(payload: AgentSubagentEventPayload): void;
}

const subscribeToAgentEvents = (listener: AgentEventListener, subscribe?: WebSocketEventBatchSubscribe): Array<() => void> => {
    const events = [
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.turnStarted, handler: (payload) => listener.onTurnStarted(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.itemStarted, handler: (payload) => listener.onItemStarted(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.itemDelta, handler: (payload) => listener.onItemDelta(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.itemCompleted, handler: (payload) => listener.onItemCompleted(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.toolCallCreated, handler: (payload) => listener.onToolCallCreated(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.toolCallStarted, handler: (payload) => listener.onToolCallStarted(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.toolCallCompleted, handler: (payload) => listener.onToolCallCompleted(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.turnCompleted, handler: (payload) => listener.onTurnCompleted(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.turnError, handler: (payload) => listener.onTurnError(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.todoUpdated, handler: (payload) => listener.onTodoUpdated(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.planUpdated, handler: (payload) => listener.onPlanUpdated(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.modeChanged, handler: (payload) => listener.onModeChanged(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.subagentSpawned, handler: (payload) => listener.onSubagentUpdated(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.subagentRunning, handler: (payload) => listener.onSubagentUpdated(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.subagentCompleted, handler: (payload) => listener.onSubagentUpdated(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.subagentMaxIterations, handler: (payload) => listener.onSubagentUpdated(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.subagentError, handler: (payload) => listener.onSubagentUpdated(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.subagentAbandoned, handler: (payload) => listener.onSubagentUpdated(payload) }),
        createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.subagentCancelled, handler: (payload) => listener.onSubagentUpdated(payload) })
    ];
    return [subscribeManagedWebSocketContracts({ label: 'AgentEventSubscriptions', events, ...(subscribe ? { subscribe } : {}) })];
};

export { subscribeToAgentEvents };
export type { AgentEventListener };
