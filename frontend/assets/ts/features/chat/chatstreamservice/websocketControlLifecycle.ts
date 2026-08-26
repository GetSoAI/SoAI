/* SoAI - Chat WebSocket control lifecycle [frontend/assets/ts/features/chat/chatstreamservice/websocketControlLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { ChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { ChatStreamOwnerDispatch } from '@features/chat/chatstreamservice/ownerDispatch.ts';
import type { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import { isSuppressedCommandErrorEvent } from '@features/chat/chatstreamservice/websocketBridgeSuppression.ts';

const log = createModuleLogger('ChatStreamWebSocketControlLifecycle', { defaultLevel: 'warn' });

interface ChatStreamWebSocketControlLifecycleOptions {
    ownerDispatch: ChatStreamOwnerDispatch;
    requestDispositions: StreamRequestDispositionRegistry;
    handleFollowerCommandError(envelope: ChatStreamCommandErrorEnvelope): void;
    handleConnected(): Promise<void>;
}

class ChatStreamWebSocketControlLifecycle {
    readonly #options: ChatStreamWebSocketControlLifecycleOptions;
    #unsubscribe: (() => void) | null = null;

    constructor(options: ChatStreamWebSocketControlLifecycleOptions) {
        this.#options = options;
    }

    initialize(): void {
        if (this.#unsubscribe !== null) return;
        this.#unsubscribe = subscribeManagedWebSocketContracts({
            label: 'ChatStreamWebSocketControlLifecycle',
            events: [
                createWebSocketContractBinding({
                    contract: WEBSOCKET_EVENT_CONTRACTS.chatStream.commandError,
                    handler: (envelope) => this.#handleCommandError(envelope)
                }),
                createWebSocketContractBinding({
                    contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
                    handler: () => {
                        void this.#options.handleConnected().catch((error) => {
                            log('warn', 'Selected conversation status sync on WebSocket connect failed', ensureError(error));
                        });
                    }
                })
            ]
        });
    }

    dispose(): void {
        this.#unsubscribe?.();
        this.#unsubscribe = null;
    }

    #handleCommandError(envelope: ChatStreamCommandErrorEnvelope): void {
        if (this.#unsubscribe === null) return;
        if (isSuppressedCommandErrorEvent(this.#options.requestDispositions, envelope, 'owner')) return;
        if (this.#options.ownerDispatch.dispatchCommandErrorEvent(envelope)) return;
        if (isSuppressedCommandErrorEvent(this.#options.requestDispositions, envelope, 'passive')) return;
        this.#options.handleFollowerCommandError(envelope);
    }
}

export { ChatStreamWebSocketControlLifecycle };
