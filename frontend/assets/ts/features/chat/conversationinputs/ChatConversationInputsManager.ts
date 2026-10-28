/* SoAI - Durable conversation input admission and observation [frontend/assets/ts/features/chat/conversationinputs/ChatConversationInputsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_STREAM_STEER_INTERRUPTED_CODE, type ConversationInputActiveState, type ConversationInputLifecycleState } from '@core/chat/protocols.ts';
import { isConversationInputTerminalState } from '@core/chat/conversationInputLifecycle.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { isAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import type { ConversationInputTerminalEvent, ConversationInputsChangedEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import type { ConversationInputAdmission } from '@core/api/contracts/chatQueueDraftContracts.ts';
import type { ConversationRegenerationReceipt, ConversationRegenerationRequest } from '@core/api/contracts/webuiMessageRegenerationContracts.ts';
import type { ChatConversationInputsManagerDependencies, ConversationInput, RetryableConversationRegeneration } from '@features/chat/conversationinputs/ConversationInputTypes.ts';
import { buildConversationInputEnqueueRequest, type ConversationInputEnqueuePayload } from '@features/chat/conversationinputs/conversationInputEnqueueRequest.ts';
import { ConversationRegenerationRetryStore } from '@features/chat/conversationinputs/ConversationRegenerationRetryStore.ts';
import { ConversationInputSettlementReconciler } from '@features/chat/conversationinputs/ConversationInputSettlementReconciler.ts';
import { ConversationInputStateStore } from '@features/chat/conversationinputs/ConversationInputStateStore.ts';
import { syncConversationInputs } from '@features/chat/conversationinputs/conversationInputSync.ts';
import { recoverAmbiguousRegenerationAdmission } from '@features/chat/conversationinputs/regenerationAdmissionRecovery.ts';
import { recoverLatestConversationRegeneration } from '@features/chat/conversationinputs/regenerationStatusRecovery.ts';
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

    hasDispatchingInput(conversationId: string): boolean {
        return this.#store.hasDispatchableHead(conversationId);
    }

    getSteeringTargetInputId(conversationId: string): string | null {
        return this.#store.getSteeringTargetInputId(conversationId);
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
            const receipt = await recoverAmbiguousRegenerationAdmission({
                admit: async () => await regenerationApi.regenerate(normalizedConversationId, admissionRequest),
                readReceipt: async () => await regenerationApi.regenerationStatus(normalizedConversationId, this.#clientId, clientRequestId),
                signal: this.#lifecycleController.signal
            });
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

    async enqueue(conversationId: string, payload: ConversationInputEnqueuePayload): Promise<ConversationInputAdmission> {
        this.initialize();
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            throw new Error('Conversation input enqueue requires a valid conversation id.');
        }
        const request = buildConversationInputEnqueueRequest(payload, this.#clientId);
        const conversationInputsApi = this.#dependencies.conversationInputsApi;
        const admit = async (): Promise<ConversationInputAdmission> => await conversationInputsApi.enqueue(normalizedConversationId, request);
        this.#store.beginAdmission(normalizedConversationId);
        try {
            const receipt = await recoverAmbiguousRegenerationAdmission({ admit, readReceipt: admit, signal: this.#lifecycleController.signal });
            if (this.#lifecycleController.signal.aborted) return receipt;
            const isDispatchableHead = this.#applyAdmissionReceipt(normalizedConversationId, receipt, (state) => ({ ...receipt, state }));
            this.#syncNoncritical(normalizedConversationId, 'Failed to reconcile admitted conversation input');
            return { ...receipt, isDispatchableHead };
        } finally {
            this.#store.completeAdmission(normalizedConversationId);
        }
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

    async resumeHeldPrompts(conversationId: string): Promise<void> {
        this.initialize();
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) return;
        const signal = this.#lifecycleController.signal;
        await raceWithAbortSignal(this.#dependencies.conversationInputsApi.resume(normalizedConversationId), signal);
        throwIfAborted(signal);
        this.#syncNoncritical(normalizedConversationId, 'Failed to reconcile resumed conversation inputs');
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
        this.#applyAdmissionReceipt(conversationId, receipt, (state) => ({
            inputId: receipt.inputId,
            inputType: 'prompt',
            text: '',
            attachmentContent: [],
            acceptedAtMs: receipt.acceptedAtMs,
            state,
            isRegeneration: true,
            isHeld: false
        }));
    }

    #applyAdmissionReceipt(conversationId: string, receipt: { inputId: string; state: ConversationInputLifecycleState; isDispatchableHead: boolean }, projectInput: (state: ConversationInputActiveState) => ConversationInput): boolean {
        try {
            if (isConversationInputTerminalState(receipt.state)) {
                this.#store.recordTerminalInput(conversationId, receipt.inputId);
                void this.#settlements.reconcile(conversationId).catch((error) => {
                    if (!this.#lifecycleController.signal.aborted) this.#dependencies.logWarning('Failed to reconcile settled conversation input admission', ensureError(error));
                });
                return false;
            }
            const isDispatchableHead = this.#store.upsertAdmittedInput(conversationId, projectInput(receipt.state), receipt.isDispatchableHead);
            this.#withdrawRegenerationRetryWhileActive(conversationId);
            return isDispatchableHead;
        } catch (error) {
            errorHandler.warn('ChatConversationInputsManager', 'Failed to project admitted conversation input', { error: ensureError(error), conversationId, inputId: receipt.inputId });
            this.#syncNoncritical(conversationId, 'Failed to reconcile admitted conversation input');
            return false;
        } finally {
            if (this.#dependencies.getCurrentConversationId() === conversationId) this.#dependencies.updateInputQueuePreview();
        }
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
            const steerFollows = event.terminalState === 'cancelled' && event.terminalCode === CHAT_STREAM_STEER_INTERRUPTED_CODE;
            this.#store.recordTerminalInput(event.convId, event.inputId, { cancelled: event.terminalState === 'cancelled', steerFollows });
            if (steerFollows) this.#syncNoncritical(event.convId, 'Failed to load the steer that follows an interrupted turn');
        }
        if (this.#dependencies.getCurrentConversationId() === event.convId) {
            this.#dependencies.updateInputQueuePreview();
        }
        this.#recoverLatestRegenerationNoncritical(event.convId);
        await this.#settlements.reconcile(event.convId);
    }
}

export { ChatConversationInputsManager };
