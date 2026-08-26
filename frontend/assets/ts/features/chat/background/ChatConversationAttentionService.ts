/* SoAI - Backend-authoritative chat conversation attention [frontend/assets/ts/features/chat/background/ChatConversationAttentionService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeConversationAttentionResourceValue } from '@core/chat/conversationAttentionSnapshot.ts';
import { CHAT_CONVERSATION_ATTENTION_SERVICE_ID, type ChatConversationTerminalIndicator } from '@core/chat/protocols.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import { WEBUI_CHAT_ATTENTION } from '@core/realtime/streammanager/resources/ids.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';

interface ConversationAttentionStream {
    resources: {
        ensureResourceStarted(resource: string, options?: { allowDiscovery?: boolean }): Promise<JsonValue | null>;
    };
    subscriptions: {
        subscribeResourceState(resource: string, listener: (snapshot: ResourceSnapshot) => void, options?: { immediate?: boolean; ensureStart?: boolean }): () => void;
    };
}

interface ChatConversationAttentionServiceDependencies {
    stream: ConversationAttentionStream;
    sendMessage(payload: JsonObject, options: { waitForConnection: boolean }): Promise<void>;
}

type AttentionRecord = {
    attentionId: number;
    assistantAtMs: number;
    terminalStatus: ChatConversationTerminalIndicator;
};

type PendingConversationAcknowledgement = {
    assistantAtMs: number;
    conversationId: string;
};

class ChatConversationAttentionService {
    readonly #dependencies: ChatConversationAttentionServiceDependencies;
    readonly #terminalIndicatorChanges = new ChangeNotificationSource();
    #records = new Map<string, AttentionRecord>();
    #unsubscribe: (() => void) | null = null;
    #authoritative = false;
    #pendingSeenThroughAttentionId: number | null = null;
    #markSeenInFlight = false;
    readonly #pendingConversationAcknowledgements = new Map<string, PendingConversationAcknowledgement>();
    readonly #conversationAcknowledgementsInFlight = new Set<string>();
    readonly #conversationAcknowledgementRetries = new Set<string>();

    constructor(dependencies: ChatConversationAttentionServiceDependencies) {
        this.#dependencies = dependencies;
    }

    async initialize(): Promise<void> {
        if (this.#unsubscribe !== null) return;
        this.#unsubscribe = this.#dependencies.stream.subscriptions.subscribeResourceState(WEBUI_CHAT_ATTENTION, (snapshot): void => this.#applyResourceSnapshot(snapshot), { immediate: true, ensureStart: false });
        await this.#dependencies.stream.resources.ensureResourceStarted(WEBUI_CHAT_ATTENTION, { allowDiscovery: true }).catch((error) => {
            const runtimeError = ensureError(error);
            if (isLifecycleCancellationError(runtimeError)) return;
            errorHandler.warn('ChatConversationAttentionService', 'Failed to initialize conversation attention', runtimeError);
        });
    }

    dispose(): void {
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.#authoritative = false;
        this.#pendingSeenThroughAttentionId = null;
        this.#markSeenInFlight = false;
        this.#pendingConversationAcknowledgements.clear();
        this.#conversationAcknowledgementsInFlight.clear();
        this.#conversationAcknowledgementRetries.clear();
        if (this.#records.size) {
            this.#records.clear();
            this.#terminalIndicatorChanges.notify();
        }
    }

    getConversationTerminalIndicator(conversationId: string | null): ChatConversationTerminalIndicator | null {
        if (!this.#authoritative || typeof conversationId !== 'string') return null;
        const normalized = conversationId.trim();
        return normalized ? (this.#records.get(normalized)?.terminalStatus ?? null) : null;
    }

    getTerminalIndicatorSummary(): ChatConversationTerminalIndicator | null {
        if (!this.#authoritative) return null;
        let hasComplete = false;
        for (const record of this.#records.values()) {
            if (record.terminalStatus === 'error') return 'error';
            hasComplete = true;
        }
        return hasComplete ? 'complete' : null;
    }

    subscribeTerminalIndicators(handler: () => void): () => void {
        return this.#terminalIndicatorChanges.subscribe(handler);
    }

    markCurrentSnapshotSeen(): void {
        if (!this.#authoritative || !this.#records.size) return;
        let watermark = 0;
        for (const record of this.#records.values()) watermark = Math.max(watermark, record.attentionId);
        this.#pendingSeenThroughAttentionId = Math.max(this.#pendingSeenThroughAttentionId ?? 0, watermark);
        this.#sendPendingMarkSeen();
    }

    markConversationSeen(conversationId: string, assistantAtMs: number): void {
        const normalized = conversationId.trim();
        if (!normalized || !Number.isSafeInteger(assistantAtMs) || assistantAtMs <= 0) return;
        const acknowledgementKey = this.#conversationAcknowledgementKey(normalized, assistantAtMs);
        this.#pendingConversationAcknowledgements.set(acknowledgementKey, {
            assistantAtMs,
            conversationId: normalized
        });
        this.#sendPendingConversationAcknowledgement(acknowledgementKey);
    }

    markTrackedConversationSeen(conversationId: string): void {
        if (!this.#authoritative) return;
        const normalized = conversationId.trim();
        if (!normalized) return;
        const record = this.#records.get(normalized);
        if (!record) return;
        this.markConversationSeen(normalized, record.assistantAtMs);
    }

    #sendPendingConversationAcknowledgement(acknowledgementKey: string): void {
        const acknowledgement = this.#pendingConversationAcknowledgements.get(acknowledgementKey);
        if (!acknowledgement || this.#conversationAcknowledgementsInFlight.has(acknowledgementKey)) return;
        this.#conversationAcknowledgementsInFlight.add(acknowledgementKey);
        void this.#dependencies
            .sendMessage(
                {
                    type: WEBSOCKET_MESSAGE_TYPES.CONVERSATION_ATTENTION_MARK_SEEN,
                    'conversation_id': acknowledgement.conversationId,
                    'assistant_at_ms': acknowledgement.assistantAtMs
                },
                { waitForConnection: true }
            )
            .catch((error) => {
                errorHandler.warn('ChatConversationAttentionService', 'Failed to mark conversation seen', ensureError(error));
            })
            .finally(() => {
                this.#conversationAcknowledgementsInFlight.delete(acknowledgementKey);
                const retryRequested = this.#conversationAcknowledgementRetries.delete(acknowledgementKey);
                if (retryRequested && this.#pendingConversationAcknowledgements.has(acknowledgementKey)) {
                    this.#sendPendingConversationAcknowledgement(acknowledgementKey);
                }
            });
    }

    #applyResourceSnapshot(snapshot: ResourceSnapshot): void {
        if (snapshot.status !== 'ready') {
            const changed = this.#authoritative || this.#records.size > 0;
            this.#authoritative = false;
            this.#records.clear();
            if (changed) this.#terminalIndicatorChanges.notify();
            return;
        }
        const entries = decodeConversationAttentionResourceValue(snapshot.value).conversations;
        const nextRecords = new Map<string, AttentionRecord>();
        for (const entry of entries) {
            nextRecords.set(entry.conversationId, {
                attentionId: entry.attentionId,
                assistantAtMs: entry.assistantAtMs,
                terminalStatus: entry.terminalStatus
            });
        }
        const changed = !this.#recordsEqual(nextRecords);
        this.#records = nextRecords;
        this.#authoritative = true;
        const pendingWatermark = this.#pendingSeenThroughAttentionId;
        if (pendingWatermark !== null) {
            const pendingStillPresent = [...nextRecords.values()].some((record) => record.attentionId <= pendingWatermark);
            if (pendingStillPresent) this.#sendPendingMarkSeen();
            else this.#pendingSeenThroughAttentionId = null;
        }
        for (const [acknowledgementKey, acknowledgement] of this.#pendingConversationAcknowledgements) {
            if (nextRecords.get(acknowledgement.conversationId)?.assistantAtMs !== acknowledgement.assistantAtMs) {
                this.#pendingConversationAcknowledgements.delete(acknowledgementKey);
                this.#conversationAcknowledgementRetries.delete(acknowledgementKey);
                continue;
            }
            if (this.#conversationAcknowledgementsInFlight.has(acknowledgementKey)) {
                this.#conversationAcknowledgementRetries.add(acknowledgementKey);
                continue;
            }
            this.#sendPendingConversationAcknowledgement(acknowledgementKey);
        }
        if (changed) this.#terminalIndicatorChanges.notify();
    }

    #recordsEqual(nextRecords: Map<string, AttentionRecord>): boolean {
        if (this.#records.size !== nextRecords.size) return false;
        for (const [conversationId, nextRecord] of nextRecords) {
            const currentRecord = this.#records.get(conversationId);
            if (!currentRecord || currentRecord.attentionId !== nextRecord.attentionId || currentRecord.assistantAtMs !== nextRecord.assistantAtMs || currentRecord.terminalStatus !== nextRecord.terminalStatus) return false;
        }
        return true;
    }

    #conversationAcknowledgementKey(conversationId: string, assistantAtMs: number): string {
        return `${conversationId}\u0000${assistantAtMs}`;
    }

    #sendPendingMarkSeen(): void {
        const watermark = this.#pendingSeenThroughAttentionId;
        if (watermark === null || this.#markSeenInFlight) return;
        this.#markSeenInFlight = true;
        let sent = false;
        void this.#dependencies
            .sendMessage(
                {
                    type: WEBSOCKET_MESSAGE_TYPES.CONVERSATION_ATTENTION_MARK_SEEN,
                    'seen_through_attention_id': watermark
                },
                { waitForConnection: true }
            )
            .then(() => {
                sent = true;
            })
            .catch((error) => {
                errorHandler.warn('ChatConversationAttentionService', 'Failed to mark conversation attention seen', ensureError(error));
            })
            .finally(() => {
                this.#markSeenInFlight = false;
                if (sent && this.#pendingSeenThroughAttentionId !== null && this.#pendingSeenThroughAttentionId > watermark) {
                    this.#sendPendingMarkSeen();
                }
            });
    }
}

export { ChatConversationAttentionService, CHAT_CONVERSATION_ATTENTION_SERVICE_ID };
