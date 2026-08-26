/* SoAI - Settings feature MCP realtime controller [frontend/assets/ts/features/settings/mcp/mcpRealtimeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';

const MCP_REALTIME_DEBOUNCE_MS = 120;
const bindMcpRealtime = (host: McpManagerHost, reload: () => Promise<boolean>): (() => void) => {
    const debouncedReload = host.services.createDebouncedHandler((): void => {
        void reload().catch((error) => {
            host.execution.feedback.handle(ensureError(error), 'MCP realtime reload');
        });
    }, MCP_REALTIME_DEBOUNCE_MS);
    let unsubscribe: (() => void) | null = null;
    try {
        unsubscribe = subscribeManagedWebSocketContracts({
            label: 'McpRealtime',
            events: [
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.notification, handler: debouncedReload }),
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.toolsChanged, handler: debouncedReload }),
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.resourcesChanged, handler: debouncedReload }),
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.promptsChanged, handler: debouncedReload }),
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.serverStarted, handler: debouncedReload }),
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.serverAdded, handler: debouncedReload }),
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.serverRemoved, handler: debouncedReload }),
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.serverConnected, handler: debouncedReload }),
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.serverDisconnected, handler: debouncedReload }),
                createWebSocketContractBinding({ contract: WEBSOCKET_EVENT_CONTRACTS.mcp.toolInvoked, handler: debouncedReload })
            ]
        });
    } catch (subscriptionError) {
        debouncedReload.cancel();
        runCleanup(unsubscribe, (runtimeError) => {
            host.execution.feedback.handle(runtimeError, 'MCP realtime cleanup');
        });
        throw ensureError(subscriptionError);
    }
    return (): void => {
        debouncedReload.cancel();
        runCleanup(unsubscribe, (runtimeError) => {
            host.execution.feedback.handle(runtimeError, 'MCP realtime cleanup');
        });
        unsubscribe = null;
    };
};

export { bindMcpRealtime };
