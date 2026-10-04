/* SoAI - Durable conversation input admission and observation [frontend/assets/ts/features/chat/conversationinputs/ChatConversationInputsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { isAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { containsSoaiPathToken } from '@core/soailinks/codec.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ConversationInputTerminalEvent, ConversationInputsChangedEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import type { ConversationInputAdmission } from '@core/api/contracts/chatQueueDraftContracts.ts';
import type { ConversationRegenerationReceipt, ConversationRegenerationRequest } from '@core/api/contracts/webuiMessageRegenerationContracts.ts';
import type { ChatContentSegment } from '@features/chat/ChatTypes.ts';
import type { ChatConversationInputsManagerDependencies, ConversationInput, RetryableConversationRegeneration } from '@features/chat/conversationinputs/ConversationInputTypes.ts';
import { ConversationRegenerationRetryStore } from '@features/chat/conversationinputs/ConversationRegenerationRetryStore.ts';
import { ConversationInputSettlementReconciler } from '@features/chat/conversationinputs/ConversationInputSettlementReconciler.ts';
import { ConversationInputStateStore } from '@features/chat/conversationinputs/ConversationInputStateStore.ts';
import { syncConversationInputs } from '@features/chat/conversationinputs/conversationInputSync.ts';
import { recoverAmbiguousRegenerationAdmission } from '@features/chat/conversationinputs/regenerationAdmissionRecovery.ts';
import { recoverLatestConversationRegeneration } from '@features/chat/conversationinputs/regenerationStatusRecovery.ts';
import { serializeStorageContentPart } from '@features/chat/storage/messageNormalization.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

class ChatConversationInputsManager {
    readonly #dependencies: ChatConversationInputsManagerDependencies;
    readonly #store = new ConversationInputStateStore();
    readonly #lifecycleController = new AbortController();
    readonly #clientId = windowIdentity.current();
    readonly #settlements: ConversationInputSettlementReconciler;
    readonly #regenerationRetries = new ConversationRegenerationRetryStore();
    readonly #latestRegenerationReads = new Map<string, LatestRequestController>();
    #unsubscribe: (() => void) | null = null;
    #initialized = false;
    #disposed = false;

    constructor(dependencies: ChatConversationInputsManagerDependencies) {
        this.#dependencies = dependencies;
        this.#settlements = new ConversationInputSettlementReconciler({ store: this.#store, signal: this.#lifecycleController.signal, reconcileSettledConversationInputs: dependencies.reconcileSettledConversationInputs });
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
        this.#settlements.dispose();
        for (const latestRead of this.#latestRegenerationReads.values()) latestRead.invalidate();
        this.#latestRegenerationReads.clear();
        this.#regenerationRetries.reset();
        this.#store.reset();
    }

    getQueuedPrompts(conversationId: string): ConversationInput[] {
        return this.#store.getQueuedInputs(conversationId);
    }

    getRetryableRegeneration(conversationId: string): RetryableConversationRegeneration | null {
        return this.#store.hasActiveInputs(conversationId) ? null : this.#regenerationRetries.get(conversationId);
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
        if (this.#disposed) return;
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
        this.#withdrawRegenerationRetryWhileActive(normalizedConversationId);
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
        const signal = this.#lifecycleController.signal;
        throwIfAborted(signal);
        try {
            await raceWithAbortSignal(this.#dependencies.conversationInputsApi.cancel(normalizedConversationId, normalizedInputId), signal);
        } catch (error) {
            this.#syncNoncritical(normalizedConversationId, 'Failed to reconcile unsuccessful conversation input cancellation');
            throw ensureError(error);
        }
        throwIfAborted(signal);
        this.#store.recordCancelledInput(normalizedConversationId, normalizedInputId);
        if (this.#dependencies.getCurrentConversationId() === normalizedConversationId) {
            this.#dependencies.updateInputQueuePreview();
        }
        this.#syncNoncritical(normalizedConversationId, 'Failed to reconcile cancelled conversation input');
    }

    async #sync(conversationId: string): Promise<ConversationInput[]> {
        const inputs = await syncConversationInputs({
            conversationId,
            dependencies: this.#dependencies,
            store: this.#store,
            signal: this.#lifecycleController.signal
        });
        this.#withdrawRegenerationRetryWhileActive(conversationId);
        await this.#settlements.reconcile(conversationId);
        return inputs;
    }

    #syncNoncritical(conversationId: string, message: string): void {
        const signal = this.#lifecycleController.signal;
        if (signal.aborted) return;
        void this.#sync(conversationId).catch((error) => {
            const runtimeError = ensureError(error);
            if (!signal.aborted && !isAbortError(runtimeError)) {
                this.#dependencies.logWarning(message, runtimeError);
            }
        });
    }

    #applyRegenerationReceipt(conversationId: string, receipt: ConversationRegenerationReceipt): void {
        if (this.#lifecycleController.signal.aborted || !this.#regenerationRetries.observe(conversationId, receipt)) return;
        this.#withdrawRegenerationRetryWhileActive(conversationId);
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
        void this.#settlements.reconcile(conversationId).catch((error) => {
            if (!this.#lifecycleController.signal.aborted) {
                this.#dependencies.logWarning('Failed to reconcile completed conversation regeneration', ensureError(error));
            }
        });
    }

    #withdrawRegenerationRetryWhileActive(conversationId: string): void {
        if (!this.#store.hasActiveInputs(conversationId)) return;
        this.#latestRegenerationReads.get(conversationId)?.invalidate();
        this.#regenerationRetries.withdraw(conversationId);
    }

    #recoverLatestRegenerationNoncritical(conversationId: string): void {
        const regenerationApi = this.#dependencies.regenerationApi;
        if (!regenerationApi) return;
        const latestRead = this.#latestRegenerationReads.get(conversationId) ?? new LatestRequestController();
        this.#latestRegenerationReads.set(conversationId, latestRead);
        recoverLatestConversationRegeneration({
            conversationId,
            latestRead,
            readStatus: (statusConversationId, signal) => regenerationApi.latestRegenerationStatus(statusConversationId, { signal }),
            applyReceipt: (statusConversationId, receipt) => this.#applyRegenerationReceipt(statusConversationId, receipt),
            signal: this.#lifecycleController.signal,
            logWarning: this.#dependencies.logWarning
        });
    }

    #handleChangedEvent(event: ConversationInputsChangedEvent): void {
        if (this.#disposed) return;
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
        await this.#settlements.reconcile(event.convId);
    }
}

export { ChatConversationInputsManager };
