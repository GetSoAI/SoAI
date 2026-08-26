/* SoAI - Chat page agent realtime subscriptions manager [frontend/assets/ts/pages/chat/controllers/chatpageagent/realtimeSubscriptionsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import { updateAgentUiForConversation } from '@pages/chat/controllers/chatpageagent/effects.ts';
import { rehydrateCurrentConversationAgentRealtimeState } from '@pages/chat/controllers/chatpageagent/events.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';
import { applyToolCallLiveProjectionEvent } from '@pages/chat/controllers/chatpageagent/toolLiveProjectionEventsController.ts';

interface ChatPageAgentRealtimeSubscriptionDependencies {
    host: ChatPageAgentHost;
    state: ChatPageAgentState;
    isDisposed(): boolean;
    tryRenderAgentTurnMessage(): void;
    onToolLiveProjectionUpdated(): void;
}

interface ChatPageAgentRealtimeSubscriptions {
    webSocketConnected: () => void;
    toolLiveUpdated: () => void;
}

const subscribeChatPageAgentRealtime = (dependencies: ChatPageAgentRealtimeSubscriptionDependencies): ChatPageAgentRealtimeSubscriptions => {
    const webSocketConnected = subscribeManagedWebSocketContract({
        label: 'ChatPageAgent',
        contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
        handler: () => {
            if (dependencies.isDisposed()) {
                return;
            }
            rehydrateCurrentConversationAgentRealtimeState({
                host: dependencies.host,
                state: dependencies.state,
                tryRenderAgentTurnMessage: () => dependencies.tryRenderAgentTurnMessage(),
                updateUiForConversation: (conversation) => updateAgentUiForConversation(dependencies.host, dependencies.state, conversation)
            });
        }
    });
    const toolLiveUpdated = subscribeManagedWebSocketContract({
        label: 'ChatPageAgent',
        contract: WEBSOCKET_EVENT_CONTRACTS.toolLive.updated,
        handler: (payload) => {
            if (dependencies.isDisposed()) {
                return;
            }
            void dependencies.host.workflow
                .runWithBoundary('chat.tool.live_projection', async () => {
                    const applied = await applyToolCallLiveProjectionEvent(dependencies.host, payload, { isDisposed: () => dependencies.isDisposed(), pendingEvents: dependencies.state.pendingToolLiveProjectionEvents });
                    if (applied === 'updated') {
                        dependencies.onToolLiveProjectionUpdated();
                    }
                })
                .catch((error) => {
                    errorHandler.warn('Chat', 'Tool call live update handler failed', ensureError(error));
                });
        }
    });
    return { webSocketConnected, toolLiveUpdated };
};

export { subscribeChatPageAgentRealtime };
export type { ChatPageAgentRealtimeSubscriptions };
