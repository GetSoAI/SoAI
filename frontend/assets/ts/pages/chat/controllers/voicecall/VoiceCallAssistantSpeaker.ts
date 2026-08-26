/* SoAI - Chat page voice call assistant speaker [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallAssistantSpeaker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatMessage, ChatStreamService, ChatStreamTerminalUpdate, MessageSegment, StreamUpdate } from '@features/chat/public.ts';
import { VoiceCallAssistantSpeechCursorController, buildVoiceCallSpeechRequestKey } from '@pages/chat/controllers/voicecall/VoiceCallAssistantSpeechCursorController.ts';
import { VoiceCallSpeechBufferController } from '@pages/chat/controllers/voicecall/VoiceCallSpeechBufferController.ts';
import { VoiceCallSpeechPlaybackController } from '@pages/chat/controllers/voicecall/VoiceCallSpeechPlaybackController.ts';
import type { VoiceCallSpeechPlaybackHost, VoiceCallSpeechSegment, VoiceCallTtsSettings } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

const SPEECH_BUFFER_DRAIN_INTERVAL_MS = 250;

interface VoiceCallAssistantSpeakerHost extends PageFeedbackOwnerHost {
    speechSessionFactory: VoiceCallSpeechPlaybackHost['speechSessionFactory'];
    chatStreamService: ChatStreamService;
    getCurrentConversationId(): string | null;
    resolveMessageContentSegments(message: ChatMessage): MessageSegment[];
    resolveAssistantSpeechText(segments: MessageSegment[]): string;
    resolveTtsSettings(): VoiceCallTtsSettings;
    isUserSpeechConfirmed(): boolean;
    onAssistantCaptionSegment(text: string): void;
    onAssistantSpeechStateChange(speaking: boolean): void;
    onAssistantSpeechQueueDrained(): void;
    onAssistantSpeechPlaybackError(error: Error): void;
}

class VoiceCallAssistantSpeaker {
    #host: VoiceCallAssistantSpeakerHost;
    #active: boolean = false;
    #unsubscribe: (() => void) | null = null;
    #assistantConversationId: string | null = null;
    #assistantRequestId: string | null = null;
    #assistantTimestamp: number | null = null;
    readonly #interruptedRequestIds = new Set<string>();
    #speechBuffer = new VoiceCallSpeechBufferController();
    #playback: VoiceCallSpeechPlaybackController;
    #speechCursor: VoiceCallAssistantSpeechCursorController;
    readonly #timers = new ResourceTracker();
    #bufferDrainTimer: number | null = null;
    #nextSegmentSequence = 0;

    constructor(host: VoiceCallAssistantSpeakerHost) {
        this.#host = host;
        this.#speechCursor = new VoiceCallAssistantSpeechCursorController({
            resolveMessageContentSegments: (message) => host.resolveMessageContentSegments(message),
            resolveAssistantSpeechText: (segments) => host.resolveAssistantSpeechText(segments)
        });
        this.#playback = new VoiceCallSpeechPlaybackController({
            speechSessionFactory: host.speechSessionFactory,
            isUserSpeechConfirmed: () => host.isUserSpeechConfirmed(),
            onSegmentPlaybackStart: (text) => host.onAssistantCaptionSegment(text),
            onAssistantSpeechStateChange: (speaking) => host.onAssistantSpeechStateChange(speaking),
            onSpeechQueueDrained: () => host.onAssistantSpeechQueueDrained(),
            onPlaybackFailure: (error) => host.onAssistantSpeechPlaybackError(error),
            feedback: host.feedback
        });
    }

    isAssistantAudioActive(): boolean {
        return this.#playback.isAssistantAudioActive();
    }

    hasPendingSpeech(): boolean {
        return this.#playback.hasPendingSpeech() || this.#speechBuffer.hasPendingText();
    }

    isCurrentTerminalUpdate(update: ChatStreamTerminalUpdate): boolean {
        return this.#assistantConversationId === update.conversationId && this.#assistantRequestId === update.requestId && this.#assistantTimestamp === update.assistantTimestamp;
    }

    markTerminalized(update: ChatStreamTerminalUpdate): boolean {
        if (!this.isCurrentTerminalUpdate(update)) {
            return false;
        }
        return true;
    }

    start(): void {
        if (this.#active) {
            return;
        }
        this.#active = true;
        this.#interruptedRequestIds.clear();
        this.#playback.start();
        this.#unsubscribe = this.#host.chatStreamService.subscribe((update) => this.#handleStreamUpdate(update));
    }

    stop(): void {
        if (!this.#active) {
            return;
        }
        this.#active = false;
        this.#clearBufferDrainTimer();
        this.#timers.cleanup();
        this.#clearCurrentRequest();
        this.#interruptedRequestIds.clear();
        this.#playback.stop();
        const unsubscribe = this.#unsubscribe;
        this.#unsubscribe = null;
        if (unsubscribe) {
            unsubscribe();
        }
    }

    interrupt(): void {
        const interruptedRequestId = this.#assistantRequestId;
        if (interruptedRequestId !== null) {
            this.#interruptedRequestIds.add(interruptedRequestId);
        }
        this.#clearCurrentRequest();
        this.#playback.interrupt();
    }

    flushBufferedSpeech(): void {
        this.#enqueueSegments(this.#speechBuffer.flush(monotonicMs()));
        this.#syncBufferDrainTimer();
    }

    pause(): void {
        if (!this.#active) {
            return;
        }
        this.#playback.pause();
    }

    resume(): void {
        if (!this.#active) {
            return;
        }
        this.#enqueueSegments(this.#speechBuffer.drainReady(monotonicMs()));
        this.#playback.resume();
        this.#syncBufferDrainTimer();
    }

    #clearCurrentRequest(): void {
        this.#clearBufferDrainTimer();
        this.#assistantConversationId = null;
        this.#assistantRequestId = null;
        this.#assistantTimestamp = null;
        this.#nextSegmentSequence = 0;
        this.#speechCursor.reset();
        this.#speechBuffer.reset();
    }

    #handleStreamUpdate(update: StreamUpdate): void {
        if (!this.#active) {
            return;
        }
        const currentConversationId = toTrimmedString(this.#host.getCurrentConversationId());
        if (!currentConversationId) {
            return;
        }
        if (update.conversationId !== currentConversationId) {
            return;
        }
        const requestId = toTrimmedString(update.requestId);
        if (!requestId) {
            return;
        }
        if (this.#interruptedRequestIds.has(requestId)) {
            if (update.status !== 'streaming') {
                this.#interruptedRequestIds.delete(requestId);
            }
            return;
        }
        if (this.#host.chatStreamService.isRequestSuppressed(currentConversationId, requestId)) {
            return;
        }
        if (this.#assistantRequestId !== requestId || this.#assistantTimestamp !== update.assistantTimestamp) {
            this.#assistantConversationId = currentConversationId;
            this.#assistantRequestId = requestId;
            this.#assistantTimestamp = update.assistantTimestamp;
            this.#nextSegmentSequence = 0;
            const ttsSettings = this.#host.resolveTtsSettings();
            this.#clearBufferDrainTimer();
            this.#speechBuffer.reset();
            const requestKey = buildVoiceCallSpeechRequestKey(currentConversationId, requestId, update.assistantTimestamp);
            this.#speechCursor.beginRequest(requestKey);
            this.#playback.resetForRequest(requestKey, ttsSettings);
        }

        const delta = this.#speechCursor.resolveDelta(update);
        if (delta === null || !delta.text) {
            if (update.status !== 'streaming') {
                this.flushBufferedSpeech();
                this.#playback.finishCurrentRequest();
            }
            return;
        }
        this.#enqueueSegments(this.#speechBuffer.appendDelta(delta.text, monotonicMs()), delta.requestKey);
        this.#syncBufferDrainTimer();
        if (update.status !== 'streaming') {
            this.flushBufferedSpeech();
            this.#playback.finishCurrentRequest();
        }
    }

    #enqueueSegments(segments: string[], requestKey: string | null = null): void {
        if (!this.#active || segments.length === 0) {
            return;
        }
        if (this.#assistantRequestId === null) {
            return;
        }
        const resolvedRequestKey = requestKey ?? this.#currentRequestKey();
        if (resolvedRequestKey === null) {
            return;
        }
        const records: VoiceCallSpeechSegment[] = [];
        for (const text of segments) {
            records.push({
                requestKey: resolvedRequestKey,
                segmentSequence: this.#nextSegmentSequence,
                text
            });
            this.#nextSegmentSequence += 1;
        }
        this.#playback.enqueueSegments(records);
    }

    #currentRequestKey(): string | null {
        if (this.#assistantConversationId === null || this.#assistantRequestId === null || this.#assistantTimestamp === null) {
            return null;
        }
        return buildVoiceCallSpeechRequestKey(this.#assistantConversationId, this.#assistantRequestId, this.#assistantTimestamp);
    }

    #syncBufferDrainTimer(): void {
        if (!this.#active || !this.#speechBuffer.hasPendingText()) {
            this.#clearBufferDrainTimer();
            return;
        }
        if (this.#bufferDrainTimer !== null) {
            return;
        }
        this.#bufferDrainTimer = this.#timers.setTimeout(() => {
            this.#bufferDrainTimer = null;
            if (!this.#active) {
                return;
            }
            this.#enqueueSegments(this.#speechBuffer.drainReady(monotonicMs()));
            this.#syncBufferDrainTimer();
        }, SPEECH_BUFFER_DRAIN_INTERVAL_MS);
    }

    #clearBufferDrainTimer(): void {
        if (this.#bufferDrainTimer === null) {
            return;
        }
        this.#timers.clearTimeout(this.#bufferDrainTimer);
        this.#bufferDrainTimer = null;
    }
}

export { VoiceCallAssistantSpeaker };
