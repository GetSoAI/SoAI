/* SoAI - Chat token counter WebSocket event subscriptions [frontend/assets/ts/pages/chat/widgets/tokencounter/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import type { ChatTokenCountErrorEvent, ChatTokenCountResultEvent, ConversationBoundEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import type { ConversationUpdatedEvent } from '@core/realtime/eventcontracts/conversationContracts.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts, type WebSocketEventBatchSubscribe } from '@core/realtime/websocketBatchSubscription.ts';

interface TokenCounterEventHandlers {
    tokenCountResult: (event: ChatTokenCountResultEvent) => void;
    tokenCountError: (event: ChatTokenCountErrorEvent) => void;
    conversationUpdated: (event: ConversationUpdatedEvent) => void;
    knowledgePromptStateChanged: (event: ConversationBoundEvent) => void;
    agentModeChanged: (event: ConversationBoundEvent) => void;
}

type TokenCounterEventSubscriptionOptions = {
    handlers: TokenCounterEventHandlers;
    subscribe?: WebSocketEventBatchSubscribe;
};

const subscribeTokenCounterEvents = (options: TokenCounterEventSubscriptionOptions): (() => void) => {
    const events = [createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.chat.tokenCountResult, handler: options.handlers.tokenCountResult }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.chat.tokenCountError, handler: options.handlers.tokenCountError }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.conversation.updated, handler: options.handlers.conversationUpdated }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.chat.knowledgePromptChangedIdentity, handler: options.handlers.knowledgePromptStateChanged }), createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.agent.modeChanged, handler: options.handlers.agentModeChanged })];
    return subscribeManagedWebSocketContracts({ label: 'ChatTokenCounterController', events, ...(options.subscribe ? { subscribe: options.subscribe } : {}) });
};

export { subscribeTokenCounterEvents };
export type { TokenCounterEventHandlers };
