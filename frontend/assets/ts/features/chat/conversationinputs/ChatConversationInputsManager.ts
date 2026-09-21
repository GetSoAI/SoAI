/* SoAI - Durable conversation input admission and observation [frontend/assets/ts/features/chat/conversationinputs/ChatConversationInputsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import { isAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError, isErrorHttpStatus } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { containsSoaiPathToken } from '@core/soailinks/codec.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { sleepMsAbortable } from '@core/primitives/sleepMsAbortable.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ConversationInputTerminalEvent, ConversationInputsChangedEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import type { ConversationInputAdmission } from '@core/api/contracts/chatQueueDraftContracts.ts';
import type { ConversationRegenerationReceipt, ConversationRegenerationRequest } from '@core/api/contracts/webuiMessageRegenerationContracts.ts';
import type { ChatContentSegment } from '@features/chat/ChatTypes.ts';
import type { ChatConversationInputsManagerDependencies, ConversationInput, RetryableConversationRegeneration } from '@features/chat/conversationinputs/ConversationInputTypes.ts';
import { ConversationRegenerationRetryStore } from '@features/chat/conversationinputs/ConversationRegenerationRetryStore.ts';
import { ConversationInputStateStore } from '@features/chat/conversationinputs/ConversationInputStateStore.ts';
import { syncConversationInputs } from '@features/chat/conversationinputs/conversationInputSync.ts';
import { recoverAmbiguousRegenerationAdmission } from '@features/chat/conversationinputs/regenerationAdmissionRecovery.ts';
import { serializeStorageContentPart } from '@features/chat/storage/messageNormalization.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const SETTLEMENT_RECONCILIATION_RETRY_DELAYS_MS: readonly number[] = [250, 1000, 3000];

class ChatConversationInputsManager {
    readonly #dependencies: ChatConversationInputsManagerDependencies;
    readonly #store = new ConversationInputStateStore();
    readonly #lifecycleController = new AbortController();
    readonly #clientId = windowIdentity.current();
    readonly #settlementReconciliationByConversationId = new Map<string, Promise<void>>();
    readonly #regenerationRetries = new ConversationRegenerationRetryStore();
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
        this.#regenerationRetries.reset();
        this.#store.reset();
    }

    getQueuedPrompts(conversationId: string): ConversationInput[] {
        return this.#store.getQueuedInputs(conversationId);
    }

    getRetryableRegeneration(conversationId: string): RetryableConversationRegeneration | null {
        return this.#regenerationRetries.get(conversationId);
    }

    async retryRegeneration(conversationId: string, inputId: string, expectedLastModifiedAtMs: number): Promise<void> {
        const retry = this.#regenerationRetries.requireInput(conversationId, inputId);
        await this.regenerate(retry.conversationId, {
            expectedLastModifiedAtMs,
            target: null,
            retryInputId: inputId,
            contentPreviewFeedback: retry.regeneration.contentPreviewFeedback,
            previewContractFeedback: retry.regeneration.previewContractFeedback
        });
        this.#regenerationRetries.clearIfMatches(retry.conversationId, inputId);
        this.#dependencies.updateInputQueuePreview();
    }

    handleConversationRendered(conversationId: string | null): void {
        this.initialize();
        const changedConversationId = this.#store.recordRenderedConversation(conversationId);
        if (changedConversationId) {
            this.#recoverLatestRegenerationNoncritical(changedConversationId);
            this.#syncNoncritical(changedConversationId, 'Failed to load conversation inputs');
        }
    }

    async regenerate(conversationId: string, request: Omit<ConversationRegenerationRequest, 'clientId' | 'clientRequestId'>): Promise<ConversationRegenerationReceipt> {
        this.initialize();
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) throw new Error('Conversation regeneration requires a valid conversation id.');
        const clientRequestId = generateSecureId({ prefix: 'regenerate_req', separator: '_' });
        const admissionRequest: ConversationRegenerationRequest = {
            ...request,
            clientId: this.#clientId,
            clientRequestId
        };
        const regenerationApi = this.#dependencies.regenerationApi;
        if (!regenerationApi) throw new Error('Conversation regeneration API is unavailable.');
        this.#store.beginAdmission(normalizedConversationId);
        try {
            let receipt: ConversationRegenerationReceipt;
            try {
                receipt = await regenerationApi.regenerate(normalizedConversationId, admissionRequest);
            } catch (admissionError) {
                const runtimeError = ensureError(admissionError);
                if (!isNetworkError(runtimeError) && !isRequestTimeoutError(runtimeError)) {
                    throw runtimeError;
                }
                receipt = await recoverAmbiguousRegenerationAdmission({
                    conversationId: normalizedConversationId,
                    clientId: this.#clientId,
                    clientRequestId,
                    admissionError: runtimeError,
                    signal: this.#lifecycleController.signal,
                    readStatus: async (statusConversationId, clientId, requestId) => await regenerationApi.regenerationStatus(statusConversationId, clientId, requestId)
                });
            }
            this.#applyRegenerationReceipt(normalizedConversationId, receipt);
            this.#syncNoncritical(normalizedConversationId, 'Failed to reconcile admitted conversation regeneration');
            return receipt;
        } finally {
            this.#store.completeAdmission(normalizedConversationId);
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

    #applyRegenerationReceipt(conversationId: string, receipt: ConversationRegenerationReceipt): void {
        this.#regenerationRetries.observe(conversationId, receipt);
        if (this.#dependencies.getCurrentConversationId() === conversationId) this.#dependencies.updateInputQueuePreview();
        if (receipt.state === 'pending' || receipt.state === 'materializing' || receipt.state === 'running' || receipt.state === 'input_required') {
            this.#store.upsertAdmittedInput(
                conversationId,
                {
                    inputId: receipt.inputId,
                    inputType: 'prompt',
                    text: '',
                    attachmentContent: [],
                    acceptedAtMs: receipt.acceptedAtMs,
                    state: receipt.state,
                    isRegeneration: true
                },
                receipt.isDispatchableHead
            );
            if (this.#dependencies.getCurrentConversationId() === conversationId) this.#dependencies.updateInputQueuePreview();
            return;
        }
        this.#store.recordTerminalInput(conversationId, receipt.inputId);
        void this.#reconcilePendingSettlements(conversationId).catch((error) => {
            if (!this.#lifecycleController.signal.aborted) {
                this.#dependencies.logWarning('Failed to reconcile completed conversation regeneration', ensureError(error));
            }
        });
    }

    #recoverLatestRegenerationNoncritical(conversationId: string): void {
        const regenerationApi = this.#dependencies.regenerationApi;
        if (!regenerationApi) return;
        void regenerationApi
            .regenerationStatus(conversationId)
            .then((receipt) => {
                this.#applyRegenerationReceipt(conversationId, receipt);
            })
            .catch((error) => {
                if (!isErrorHttpStatus(error, 404) && !this.#lifecycleController.signal.aborted) {
                    this.#dependencies.logWarning('Failed to recover conversation regeneration', ensureError(error));
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
        this.#recoverLatestRegenerationNoncritical(event.convId);
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
