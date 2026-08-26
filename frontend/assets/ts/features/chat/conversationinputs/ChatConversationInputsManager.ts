/* SoAI - Durable conversation input admission and observation [frontend/assets/ts/features/chat/conversationinputs/ChatConversationInputsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { containsSoaiPathToken } from '@core/soailinks/codec.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { sleepMsAbortable } from '@core/primitives/sleepMsAbortable.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ConversationInputTerminalEvent, ConversationInputsChangedEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import type { ConversationInputAdmission } from '@core/api/contracts/chatQueueDraftContracts.ts';
import type { ChatContentSegment } from '@features/chat/ChatTypes.ts';
import type { ChatConversationInputsManagerDependencies, ConversationInput } from '@features/chat/conversationinputs/ConversationInputTypes.ts';
import { ConversationInputStateStore } from '@features/chat/conversationinputs/ConversationInputStateStore.ts';
import { syncConversationInputs } from '@features/chat/conversationinputs/conversationInputSync.ts';
import { serializeStorageContentPart } from '@features/chat/storage/messageNormalization.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const SETTLEMENT_RECONCILIATION_RETRY_DELAYS_MS: readonly number[] = [250, 1000, 3000];

class ChatConversationInputsManager {
    readonly #dependencies: ChatConversationInputsManagerDependencies;
    readonly #store = new ConversationInputStateStore();
    readonly #lifecycleController = new AbortController();
    readonly #clientId = windowIdentity.current();
    readonly #settlementReconciliationByConversationId = new Map<string, Promise<void>>();
    #unsubscribe: (() => void) | null = null;
    #initialized = false;
    #disposed = false;

    constructor(dependencies: ChatConversationInputsManagerDependencies) {
        this.#dependencies = dependencies;
    }

    initialize(): void {
        if (this.#initialized || this.#disposed) {
            return;
        }
        this.#initialized = true;
        const subscribe = this.#dependencies.subscribeConversationInputEvents;
        if (subscribe) {
            this.#unsubscribe = subscribe({
                inputsChanged: (event) => this.#handleChangedEvent(event),
                inputTerminal: async (event) => await this.#handleTerminalEvent(event)
            });
        }
    }

    dispose(): void {
        if (this.#disposed) {
            return;
        }
        this.#disposed = true;
        this.#lifecycleController.abort();
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.#settlementReconciliationByConversationId.clear();
        this.#store.reset();
    }

    getQueuedPrompts(conversationId: string): ConversationInput[] {
        return this.#store.getQueuedInputs(conversationId);
    }

    handleConversationRendered(conversationId: string | null): void {
        this.initialize();
        const changedConversationId = this.#store.recordRenderedConversation(conversationId);
        if (changedConversationId) {
            this.#syncNoncritical(changedConversationId, 'Failed to load conversation inputs');
        }
    }

    handleStreamTerminal(conversationId: string): void {
        this.#syncNoncritical(conversationId, 'Failed to reconcile terminal conversation inputs');
    }

    async enqueue(conversationId: string, payload: { intent: 'queued' | 'steer'; text: string | null; sourceText: string | null; attachmentContent: readonly ChatContentSegment[] }): Promise<ConversationInputAdmission> {
        this.initialize();
        const signal = this.#lifecycleController.signal;
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            throw new Error('Conversation input enqueue requires a valid conversation id.');
        }
        const text = toTrimmedString(payload.text) || null;
        const promptHistoryText = toTrimmedString(payload.sourceText) || null;
        const attachmentContent: JsonObject[] = [];
        for (const entry of payload.attachmentContent) {
            const serialized = serializeStorageContentPart(entry);
            if (!isJsonObject(serialized)) {
                throw new Error('Conversation input attachment_content entries must serialize to objects.');
            }
            attachmentContent.push(serialized);
        }
        if (text === null && attachmentContent.length === 0) {
            throw new Error('Conversation input enqueue requires text or attachment_content.');
        }
        if (text !== null && promptHistoryText === null) throw new Error('Conversation input source text must accompany textual input.');
        if (text === null && promptHistoryText !== null && !containsSoaiPathToken(promptHistoryText)) throw new Error('Attachment-only conversation input cannot include source text.');
        const created = await raceWithAbortSignal(
            this.#dependencies.conversationInputsApi.enqueue(normalizedConversationId, {
                inputType: payload.intent === 'steer' ? 'steer' : 'prompt',
                text,
                promptHistoryText,
                attachmentContent,
                clientId: this.#clientId,
                clientRequestId: generateSecureId({ prefix: 'cinput_req', separator: '_' })
            }),
            signal
        );
        throwIfAborted(signal);
        this.#store.upsertAdmittedInput(normalizedConversationId, created, created.isDispatchableHead);
        if (this.#dependencies.getCurrentConversationId() === normalizedConversationId) {
            this.#dependencies.updateInputQueuePreview();
        }
        this.#syncNoncritical(normalizedConversationId, 'Failed to reconcile admitted conversation input');
        return created;
    }

    async cancelPrompt(conversationId: string, inputId: string): Promise<void> {
        this.initialize();
        const normalizedConversationId = normalizeConversationId(conversationId);
        const normalizedInputId = toTrimmedString(inputId);
        if (!normalizedConversationId || !normalizedInputId) {
            return;
        }
        await raceWithAbortSignal(this.#dependencies.conversationInputsApi.cancel(normalizedConversationId, normalizedInputId), this.#lifecycleController.signal);
        this.#store.recordCancelledInput(normalizedConversationId, normalizedInputId);
        if (this.#dependencies.getCurrentConversationId() === normalizedConversationId) {
            this.#dependencies.updateInputQueuePreview();
        }
        await this.#sync(normalizedConversationId);
    }

    async #sync(conversationId: string): Promise<ConversationInput[]> {
        const inputs = await syncConversationInputs({
            conversationId,
            dependencies: this.#dependencies,
            store: this.#store,
            signal: this.#lifecycleController.signal
        });
        await this.#reconcilePendingSettlements(conversationId);
        return inputs;
    }

    #syncNoncritical(conversationId: string, message: string): void {
        void this.#sync(conversationId).catch((error) => {
            const runtimeError = ensureError(error);
            if (!isAbortError(runtimeError)) {
                this.#dependencies.logWarning(message, runtimeError);
            }
        });
    }

    #handleChangedEvent(event: ConversationInputsChangedEvent): void {
        if (this.#disposed) {
            return;
        }
        this.#syncNoncritical(event.convId, 'Failed to reconcile changed conversation inputs');
    }

    async #handleTerminalEvent(event: ConversationInputTerminalEvent): Promise<void> {
        if (this.#disposed) {
            return;
        }
        if (event.terminalState === 'cancelled' && event.sourceMessageId === null) {
            this.#store.recordCancelledInput(event.convId, event.inputId);
        } else {
            this.#store.recordTerminalInput(event.convId, event.inputId);
        }
        if (this.#dependencies.getCurrentConversationId() === event.convId) {
            this.#dependencies.updateInputQueuePreview();
        }
        await this.#reconcilePendingSettlements(event.convId);
    }

    async #reconcilePendingSettlements(conversationId: string): Promise<void> {
        const signal = this.#lifecycleController.signal;
        while (!signal.aborted) {
            const activeReconciliation = this.#settlementReconciliationByConversationId.get(conversationId);
            if (activeReconciliation) {
                await raceWithAbortSignal(activeReconciliation, signal);
                continue;
            }
            const inputIds = this.#store.takePendingSettlements(conversationId);
            if (inputIds.length === 0) {
                return;
            }
            const reconciliation = this.#reconcileSettlementBatch(conversationId, inputIds);
            this.#settlementReconciliationByConversationId.set(conversationId, reconciliation);
            try {
                await raceWithAbortSignal(reconciliation, signal);
            } finally {
                if (this.#settlementReconciliationByConversationId.get(conversationId) === reconciliation) {
                    this.#settlementReconciliationByConversationId.delete(conversationId);
                }
            }
        }
    }

    async #reconcileSettlementBatch(conversationId: string, inputIds: readonly string[]): Promise<void> {
        const signal = this.#lifecycleController.signal;
        for (let attemptIndex = 0; ; attemptIndex += 1) {
            try {
                await this.#dependencies.reconcileSettledConversationInputs(conversationId);
                if (!signal.aborted) {
                    this.#store.completeSettlements(conversationId, inputIds);
                }
                return;
            } catch (error) {
                const retryDelayMs = SETTLEMENT_RECONCILIATION_RETRY_DELAYS_MS[attemptIndex];
                if (signal.aborted || retryDelayMs === undefined) {
                    if (!signal.aborted) {
                        this.#store.restorePendingSettlements(conversationId, inputIds);
                    }
                    throw error;
                }
                await sleepMsAbortable(signal, retryDelayMs);
            }
        }
    }
}

export { ChatConversationInputsManager };
