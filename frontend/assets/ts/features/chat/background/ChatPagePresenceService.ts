/* SoAI - Chat feature page presence service [frontend/assets/ts/features/chat/background/ChatPagePresenceService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_PAGE_PRESENCE_SERVICE_ID } from '@core/chat/protocols.ts';
import { requireDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import { isWebSocketReconnectInterruption } from '@core/websocketclient/connectionInterruption.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import type { ChatPresentationState } from '@features/chat/chatstreamservice/contracts.ts';

const createPresenceId = (): string => generateSecureId({ prefix: 'chat-presence', format: 'hex', separator: '-' });
const PRESENCE_HEARTBEAT_INTERVAL_MS = 10_000;

class ChatPagePresenceService {
    readonly #deviceId = createPresenceId();
    readonly #tabId = windowIdentity.current();
    #mountedCount = 0;
    #pageVisible = false;
    #conversationId: string | null = null;
    #activeConversationId: string | null = null;
    #reportedPresentationConversationId: string | null = null;
    #reportedPresentationVisible = false;
    #activeConversationChangeHandler: ((conversationId: string | null) => void) | null = null;
    #presentationStateChangeHandler: ((state: ChatPresentationState) => void) | null = null;
    #document: Document | null = null;
    #window: Window | null = null;
    #cleanupBindings: (() => void) | null = null;
    #cleanupWebSocketConnected: (() => void) | null = null;
    #heartbeatTimerId: number | null = null;

    enter(): () => void {
        this.#mountedCount += 1;
        this.#ensureBindings();
        this.#sendPresence(true);
        let disposed = false;
        return () => {
            if (disposed) {
                return;
            }
            disposed = true;
            if (this.#mountedCount > 0) {
                this.#mountedCount -= 1;
            }
            this.#sendPresence();
            if (this.#mountedCount === 0) {
                this.#cleanupBindings?.();
                this.#cleanupWebSocketConnected?.();
                this.#cleanupBindings = null;
                this.#cleanupWebSocketConnected = null;
                this.#stopHeartbeat();
                this.#document = null;
                this.#window = null;
            }
        };
    }

    setConversationId(conversationId: string | null): void {
        this.#conversationId = normalizeConversationId(conversationId) || null;
        this.#sendPresence();
    }

    setPageVisible(isVisible: boolean): void {
        this.#pageVisible = isVisible;
        this.#sendPresence();
    }

    isActivelyViewingConversation(conversationId: string | null): boolean {
        const normalized = normalizeConversationId(conversationId);
        return Boolean(normalized && this.#resolveActiveConversationId() === normalized);
    }

    setActiveConversationChangeHandler(handler: (conversationId: string | null) => void): () => void {
        this.#activeConversationChangeHandler = handler;
        return () => {
            if (this.#activeConversationChangeHandler === handler) {
                this.#activeConversationChangeHandler = null;
            }
        };
    }

    setPresentationStateChangeHandler(handler: (state: ChatPresentationState) => void): () => void {
        this.#presentationStateChangeHandler = handler;
        handler(this.#resolvePresentationState());
        return () => {
            if (this.#presentationStateChangeHandler === handler) {
                this.#presentationStateChangeHandler = null;
            }
        };
    }

    #ensureBindings(): void {
        if (this.#cleanupBindings) {
            return;
        }
        const documentRef = requireDocument();
        const windowRef = documentRef.defaultView;
        if (!windowRef) {
            throw new Error('ChatPagePresenceService requires a Window');
        }
        const syncPresence = (): void => this.#sendPresence();
        documentRef.addEventListener('visibilitychange', syncPresence);
        windowRef.addEventListener('focus', syncPresence);
        windowRef.addEventListener('blur', syncPresence);
        this.#document = documentRef;
        this.#window = windowRef;
        this.#cleanupWebSocketConnected = subscribeManagedWebSocketContract({
            label: 'ChatPagePresenceService',
            contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
            handler: () => this.#sendPresence(true)
        });
        this.#cleanupBindings = () => {
            documentRef.removeEventListener('visibilitychange', syncPresence);
            windowRef.removeEventListener('focus', syncPresence);
            windowRef.removeEventListener('blur', syncPresence);
        };
    }

    #resolveActiveConversationId(): string | null {
        const presentationConversationId = this.#resolvePresentationConversationId();
        const documentRef = this.#document;
        const windowRef = this.#window;
        const active = presentationConversationId !== null && documentRef !== null && windowRef !== null && documentRef.hasFocus();
        return active ? presentationConversationId : null;
    }

    #resolvePresentationConversationId(): string | null {
        const documentRef = this.#document;
        const visible = this.#mountedCount > 0 && this.#pageVisible && documentRef !== null && documentRef.visibilityState === 'visible' && this.#conversationId !== null;
        return visible ? this.#conversationId : null;
    }

    #resolvePresentationState(): ChatPresentationState {
        return {
            conversationId: this.#conversationId,
            visible: this.#resolvePresentationConversationId() !== null
        };
    }

    #sendPresence(force = false): void {
        const presentationConversationId = this.#resolvePresentationConversationId();
        const presentationVisible = presentationConversationId !== null;
        const presentationStateChanged = this.#reportedPresentationConversationId !== this.#conversationId || this.#reportedPresentationVisible !== presentationVisible;
        if (presentationStateChanged) {
            this.#reportedPresentationConversationId = this.#conversationId;
            this.#reportedPresentationVisible = presentationVisible;
            this.#presentationStateChangeHandler?.({ conversationId: this.#conversationId, visible: presentationVisible });
        }
        const activeConversationId = this.#resolveActiveConversationId();
        const changed = this.#activeConversationId !== activeConversationId;
        if (changed) {
            this.#activeConversationId = activeConversationId;
            this.#activeConversationChangeHandler?.(activeConversationId);
        }
        this.#syncHeartbeat(activeConversationId);
        if (!changed && !force) {
            return;
        }
        const websocketClient = getWebSocketClient();
        if (!websocketClient.isConnected()) {
            return;
        }
        void websocketClient
            .sendMessage(
                {
                    type: WEBSOCKET_MESSAGE_TYPES.CONVERSATION_PRESENCE_UPDATE,
                    'device_id': this.#deviceId,
                    'tab_id': this.#tabId,
                    'conversation_id': activeConversationId,
                    'is_visible': activeConversationId !== null,
                    'has_focus': activeConversationId !== null
                },
                { waitForConnection: false }
            )
            .catch((error) => {
                const runtimeError = ensureError(error);
                if (isWebSocketReconnectInterruption(runtimeError)) {
                    return;
                }
                errorHandler.warn('ChatPagePresenceService', 'Failed to publish chat presence', runtimeError);
            });
    }

    #syncHeartbeat(activeConversationId: string | null): void {
        if (activeConversationId === null) {
            this.#stopHeartbeat();
            return;
        }
        if (this.#heartbeatTimerId !== null || this.#window === null) {
            return;
        }
        this.#heartbeatTimerId = this.#window.setInterval(() => this.#sendPresence(true), PRESENCE_HEARTBEAT_INTERVAL_MS);
    }

    #stopHeartbeat(): void {
        if (this.#heartbeatTimerId === null || this.#window === null) {
            this.#heartbeatTimerId = null;
            return;
        }
        this.#window.clearInterval(this.#heartbeatTimerId);
        this.#heartbeatTimerId = null;
    }
}

export { ChatPagePresenceService, CHAT_PAGE_PRESENCE_SERVICE_ID };
