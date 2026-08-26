/* SoAI - Voice call turn management [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallTurnManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { ChatContentSegment } from '@features/chat/public.ts';
import { isString } from '@core/typeGuards.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { QueuedSendGuardContext, QueuedSendGuardResult, QueuedSendOutcome } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';
import type { VoiceCallUiStatus, VoiceCallUtterance } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';
import type { VoiceCallConversationState } from '@pages/chat/controllers/voicecall/VoiceCallConversationState.ts';

interface VoiceCallTurnSpeaker {
    interrupt(): void;
    flushBufferedSpeech(): void;
    hasPendingSpeech(): boolean;
    isAssistantAudioActive(): boolean;
}

interface VoiceCallTurnTranscriber {
    transcribe(utterance: VoiceCallUtterance, sttModel: string, signal: AbortSignal): Promise<string>;
}

interface VoiceCallTurnControllerHost {
    getCurrentConversationId(): string | null;
    isConversationStreaming(conversationId: string): boolean;
    interruptStreaming(conversationId: string, reason?: string): void;
    waitForConversationIdle(conversationId: string, signal: AbortSignal): Promise<void>;
    resolveSttModel(): string;
    sendVoiceMessage(text: string, attachmentContent: readonly ChatContentSegment[], signal: AbortSignal, beforeSend: (context: QueuedSendGuardContext) => QueuedSendGuardResult): Promise<QueuedSendOutcome>;
}

interface VoiceCallTurnManagerHost extends PageFeedbackOwnerHost {
    controllerHost: VoiceCallTurnControllerHost;
    transcriber: VoiceCallTurnTranscriber;
    speaker: VoiceCallTurnSpeaker;
    isActive(): boolean;
    setStatus(status: VoiceCallUiStatus, errorText: string | null): void;
    setUserTranscript(text: string): void;
    clearAssistantCaption(): void;
    stopUnboundConversationChange(): void;
    conversationBinding: VoiceCallConversationState;
}

class VoiceCallTurnManager {
    readonly #host: VoiceCallTurnManagerHost;
    readonly #utteranceToken = new SequenceToken();
    #transcriptionAbort: AbortController | null = null;

    constructor(host: VoiceCallTurnManagerHost) {
        this.#host = host;
    }

    bindInitialConversation(): void {
        const conversationId = toTrimmedString(this.#host.controllerHost.getCurrentConversationId());
        this.#host.conversationBinding.bindInitial(conversationId ? conversationId : null);
    }

    getBoundConversationId(): string | null {
        return this.#host.conversationBinding.get();
    }

    clear(): void {
        this.#utteranceToken.invalidate();
        this.abortTranscription();
        this.#host.conversationBinding.clear();
    }

    abortTranscription(): void {
        this.#transcriptionAbort?.abort();
        this.#transcriptionAbort = null;
    }

    interruptActiveConversation(): void {
        const conversationId = this.#host.conversationBinding.get();
        if (conversationId === null || !this.#host.controllerHost.isConversationStreaming(conversationId)) {
            return;
        }
        this.#host.controllerHost.interruptStreaming(conversationId, i18n.t('chat.voiceCall.interrupted'));
    }

    handleUserSpeechStart(): void {
        this.abortTranscription();
        this.#utteranceToken.invalidate();
        this.#host.speaker.interrupt();
        this.#host.clearAssistantCaption();
        this.#host.setStatus('speaking', null);
        this.interruptActiveConversation();
    }

    handleUtterance(utterance: VoiceCallUtterance): void {
        if (!this.#host.isActive()) {
            return;
        }
        this.abortTranscription();
        const token = this.#utteranceToken.next();
        const abortController = new AbortController();
        this.#transcriptionAbort = abortController;
        this.#host.setStatus('transcribing', null);
        void this.#processUtterance(token, utterance, abortController.signal)
            .finally(() => {
                if (this.#transcriptionAbort === abortController) {
                    this.#transcriptionAbort = null;
                }
            })
            .catch((error) => {
                if (!this.#host.isActive() || !this.#utteranceToken.isActive(token) || abortController.signal.aborted) {
                    return;
                }
                const runtimeError = ensureError(error);
                this.#host.feedback.handle(runtimeError, 'Voice transcription failed');
                const failureMessage = i18n.t('chat.voiceCall.transcriptionFailed');
                this.#host.setStatus('error', failureMessage);
                this.#host.feedback.show(failureMessage, 'error');
            });
    }

    async #processUtterance(token: number, utterance: VoiceCallUtterance, signal: AbortSignal): Promise<void> {
        const sttModel = this.#host.controllerHost.resolveSttModel();
        const text = await this.#host.transcriber.transcribe(utterance, sttModel, signal);
        if (!this.#host.isActive() || !this.#utteranceToken.isActive(token)) {
            return;
        }
        const normalized = isString(text) ? text.trim() : '';
        if (!normalized) {
            this.#host.setStatus('listening', null);
            return;
        }
        this.#host.setUserTranscript(normalized);
        await this.#sendVoiceMessage(normalized, token, signal);
    }

    async #sendVoiceMessage(text: string, token: number, signal: AbortSignal): Promise<void> {
        const pendingInitialBinding = this.#host.conversationBinding.beginSend();
        try {
            this.#host.setStatus('assistantThinking', null);
            const firstOutcome = await this.#sendVoiceMessageOnce(text, token, signal);
            const outcome = firstOutcome.status === 'blocked' && firstOutcome.reason === 'streaming' ? await this.#retryAfterStreamingIdle(text, token, signal) : firstOutcome;
            if (outcome.status !== 'sent') {
                if (outcome.status === 'aborted' || !this.#host.isActive() || !this.#utteranceToken.isActive(token) || signal.aborted) {
                    return;
                }
                this.#host.setStatus('listening', null);
                return;
            }
            this.#host.speaker.flushBufferedSpeech();
            if (this.shouldResumeListening(token)) {
                this.#host.setStatus('listening', null);
            }
        } catch (error) {
            if (signal.aborted || !this.#host.isActive() || !this.#utteranceToken.isActive(token)) {
                return;
            }
            const runtimeError = ensureError(error);
            this.#host.feedback.handle(runtimeError, 'Voice message send failed');
            const failureMessage = i18n.t('chat.voiceCall.messageSendFailed');
            this.#host.setStatus('error', failureMessage);
            this.#host.feedback.show(failureMessage, 'error');
        } finally {
            if (pendingInitialBinding) {
                if (this.#host.conversationBinding.finishSend(true, this.#host.controllerHost.getCurrentConversationId())) this.#host.stopUnboundConversationChange();
            }
        }
    }

    async #sendVoiceMessageOnce(text: string, token: number, signal: AbortSignal): Promise<QueuedSendOutcome> {
        try {
            return await this.#host.controllerHost.sendVoiceMessage(text, [], signal, (context) => this.#beforeSend(context, token, signal));
        } catch (error) {
            if (isAbortError(error)) {
                return { status: 'aborted' };
            }
            throw error;
        }
    }

    async #retryAfterStreamingIdle(text: string, token: number, signal: AbortSignal): Promise<QueuedSendOutcome> {
        const conversationId = this.#host.conversationBinding.get();
        if (conversationId === null) {
            return { status: 'blocked', reason: 'conversation-mismatch' };
        }
        await this.#host.controllerHost.waitForConversationIdle(conversationId, signal);
        if (signal.aborted || !this.#host.isActive() || !this.#utteranceToken.isActive(token)) {
            return { status: 'aborted' };
        }
        return await this.#sendVoiceMessageOnce(text, token, signal);
    }

    #beforeSend(context: QueuedSendGuardContext, token: number, signal: AbortSignal): QueuedSendGuardResult {
        if (signal.aborted || !this.#host.isActive() || !this.#utteranceToken.isActive(token)) {
            return { allowed: false, reason: 'aborted' };
        }
        if (context.isStreaming) {
            return { allowed: false, reason: 'streaming' };
        }
        const currentConversationId = toTrimmedString(this.#host.controllerHost.getCurrentConversationId());
        const createdFromEmptyConversation = context.startedFromEmptyConversation && context.createdConversationForSend && context.isFirstMessage;
        if (this.#host.conversationBinding.bindCreated(context.conversationId, currentConversationId, createdFromEmptyConversation)) return true;
        return this.#host.conversationBinding.matches(context.conversationId, currentConversationId) ? true : { allowed: false, reason: 'conversation-mismatch' };
    }

    shouldResumeListening(token: number): boolean {
        const conversationId = this.#host.conversationBinding.get();
        const streaming = conversationId ? this.#host.controllerHost.isConversationStreaming(conversationId) : false;
        return this.#host.isActive() && this.#utteranceToken.isActive(token) && !streaming && !this.#host.speaker.hasPendingSpeech() && !this.#host.speaker.isAssistantAudioActive();
    }

    shouldResumeListeningCurrent(): boolean {
        return this.shouldResumeListening(this.#utteranceToken.value);
    }

    reconcileAssistantResponseStatus(): boolean {
        if (!this.shouldResumeListeningCurrent()) {
            return false;
        }
        this.#host.setStatus('listening', null);
        return true;
    }

    isInitialBindingPending(): boolean {
        return this.#host.conversationBinding.isInitialPending();
    }
}

export { VoiceCallTurnManager };
