/* SoAI - Chat feature page presence service [frontend/assets/ts/features/chat/background/ChatPagePresenceService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_PAGE_PRESENCE_SERVICE_ID, type ChatPagePresenceOwner, type ChatPagePresenceServiceContract, type ChatPresentationState } from '@core/chat/protocols.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { CleanupStack } from '@core/lifecycle/cleanupStack.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
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

const createPresenceId = (): string => generateSecureId({ prefix: 'chat-presence', format: 'hex', separator: '-' });
const PRESENCE_HEARTBEAT_INTERVAL_MS = 10_000;

interface ChatPresenceMount {
    readonly owner: ChatPagePresenceOwner;
    readonly cleanup: CleanupStack;
    active: boolean;
}

class ChatPagePresenceService implements ChatPagePresenceServiceContract {
    readonly #deviceId = createPresenceId();
    readonly #tabId = windowIdentity.current();
    readonly #mounts = new Set<ChatPresenceMount>();
    readonly #presenceUpdate = new SequenceToken();
    #presencePublicationPending = false;
    #pageVisible = false;
    #conversationId: string | null = null;
    #activeConversationId: string | null = null;
    #reportedPresentationConversationId: string | null = null;
    #reportedPresentationVisible = false;
    #activeConversationChangeHandler: ((conversationId: string | null) => void) | null = null;
    #presentationStateChangeHandler: ((state: ChatPresentationState) => void) | null = null;
    #document: Document | null = null;
    #window: Window | null = null;
    #bindings: CleanupStack | null = null;
    #heartbeatTimerId: number | null = null;

    enter(owner: ChatPagePresenceOwner): () => void {
        if (!owner.admission.isCurrent()) throw new LifecycleCancellationError('Chat presence owner is no longer current', 'chat-presence-owner-stale');
        for (const mount of this.#mounts) if (!mount.active) throwCollectedCleanupFailures(mount.cleanup.dispose());
        const mount: ChatPresenceMount = { owner, cleanup: new CleanupStack({ logError: (message, error) => errorHandler.debug('ChatPagePresenceService', message, error) }), active: true };
        this.#mounts.add(mount);
        const release = (): void => {
            mount.active = false;
            const failures = [...mount.cleanup.dispose()];
            if (failures.length === 0) this.#mounts.delete(mount);
            runCleanupStepCollectingFailure(() => this.#sendPresence(), failures);
            if (![...this.#mounts].some((entry) => entry.active)) runCleanupStepCollectingFailure(() => this.#releaseBindings(), failures);
            throwCollectedCleanupFailures(failures);
        };
        try {
            this.#ensureBindings();
            mount.cleanup.add(owner.presentation.subscribe(() => this.#sendPresence()));
            this.#sendPresence(true);
        } catch (error) {
            const failures = [ensureError(error)];
            runCleanupStepCollectingFailure(release, failures);
            throwCollectedCleanupFailures([...new Set(failures)]);
            throw ensureError(error);
        }
        return release;
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
        if (this.#bindings) {
            if (this.#bindings.status === 'active') return;
            throwCollectedCleanupFailures(this.#bindings.dispose());
            throw new LifecycleCancellationError('Chat presence bindings are being released', 'chat-presence-release-pending');
        }
        const documentRef = requireDocument();
        const windowRef = documentRef.defaultView;
        if (!windowRef) throw new Error('ChatPagePresenceService requires a Window');
        const bindings = new CleanupStack({ logError: (message, error) => errorHandler.debug('ChatPagePresenceService', message, error) });
        this.#bindings = bindings;
        this.#document = documentRef;
        this.#window = windowRef;
        const syncPresence = (): void => this.#sendPresence();
        try {
            documentRef.addEventListener('visibilitychange', syncPresence);
            bindings.add(() => documentRef.removeEventListener('visibilitychange', syncPresence));
            windowRef.addEventListener('focus', syncPresence);
            bindings.add(() => windowRef.removeEventListener('focus', syncPresence));
            windowRef.addEventListener('blur', syncPresence);
            bindings.add(() => windowRef.removeEventListener('blur', syncPresence));
            bindings.add(subscribeManagedWebSocketContract({ label: 'ChatPagePresenceService', contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected, handler: () => this.#sendPresence(true) }));
            bindings.add(() => this.#stopHeartbeat());
        } catch (error) {
            const failures = [ensureError(error)];
            runCleanupStepCollectingFailure(() => this.#releaseBindings(), failures);
            throwCollectedCleanupFailures([...new Set(failures)]);
        }
    }

    #releaseBindings(): void {
        const bindings = this.#bindings;
        if (!bindings) return;
        throwCollectedCleanupFailures(bindings.dispose());
        if (this.#bindings === bindings) {
            this.#bindings = null;
            this.#document = null;
            this.#window = null;
        }
    }

    #resolveActiveConversationId(): string | null {
        const presentationConversationId = this.#resolvePresentationConversationId();
        const documentRef = this.#document;
        const windowRef = this.#window;
        const active = presentationConversationId !== null && documentRef !== null && windowRef !== null && documentRef.hasFocus() && [...this.#mounts].some((mount) => mount.active && mount.owner.admission.isCurrent() && mount.owner.presentation.isFocused());
        return active ? presentationConversationId : null;
    }

    #resolvePresentationConversationId(): string | null {
        const documentRef = this.#document;
        const visible = [...this.#mounts].some((mount) => mount.active && mount.owner.admission.isCurrent() && mount.owner.presentation.isVisible()) && this.#pageVisible && documentRef !== null && documentRef.visibilityState === 'visible' && this.#conversationId !== null;
        return visible ? this.#conversationId : null;
    }

    #resolvePresentationState(): ChatPresentationState {
        return {
            conversationId: this.#conversationId,
            visible: this.#resolvePresentationConversationId() !== null
        };
    }

    #sendPresence(force = false): void {
        const update = this.#presenceUpdate.next();
        if (force) this.#presencePublicationPending = true;
        const presentationConversationId = this.#resolvePresentationConversationId();
        const presentationVisible = presentationConversationId !== null;
        const presentationStateChanged = this.#reportedPresentationConversationId !== this.#conversationId || this.#reportedPresentationVisible !== presentationVisible;
        if (presentationStateChanged) {
            this.#reportedPresentationConversationId = this.#conversationId;
            this.#reportedPresentationVisible = presentationVisible;
            this.#presentationStateChangeHandler?.({ conversationId: this.#conversationId, visible: presentationVisible });
        }
        if (!this.#presenceUpdate.isActive(update)) return;
        const activeConversationId = this.#resolveActiveConversationId();
        const changed = this.#activeConversationId !== activeConversationId;
        if (changed) {
            this.#presencePublicationPending = true;
            this.#activeConversationId = activeConversationId;
            this.#activeConversationChangeHandler?.(activeConversationId);
        }
        if (!this.#presenceUpdate.isActive(update)) return;
        this.#syncHeartbeat(activeConversationId);
        if (!this.#presencePublicationPending) {
            return;
        }
        const websocketClient = getWebSocketClient();
        if (!websocketClient.isConnected()) {
            return;
        }
        this.#presencePublicationPending = false;
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
