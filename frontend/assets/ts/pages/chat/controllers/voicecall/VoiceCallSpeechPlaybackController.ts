/* SoAI - Voice call speech playback controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallSpeechPlaybackController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpenAiAudioSpeechSessionClient } from '@core/api/endpoints/openaiWsAudioSpeechSession.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { VoiceCallSpeechSessionEventsController } from '@pages/chat/controllers/voicecall/VoiceCallSpeechSessionEventsController.ts';
import { VoiceCallSpeechSessionConnectionController } from '@pages/chat/controllers/voicecall/VoiceCallSpeechSessionConnectionController.ts';
import type { VoiceCallSpeechPlaybackHost, VoiceCallSpeechSegment, VoiceCallTtsSettings } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

class VoiceCallSpeechPlaybackController {
    readonly #host: VoiceCallSpeechPlaybackHost;
    readonly #generation = new SequenceToken();
    readonly #events: VoiceCallSpeechSessionEventsController;
    #active = false;
    #paused = false;
    #assistantSpeaking = false;
    #assistantAudioActive = false;
    #requestKey: string | null = null;
    #settings: VoiceCallTtsSettings | null = null;
    #session: OpenAiAudioSpeechSessionClient | null = null;
    #sessionStarting = false;
    #queue: VoiceCallSpeechSegment[] = [];
    #sending = false;
    #finishRequested = false;
    #drainNotified = true;

    constructor(host: VoiceCallSpeechPlaybackHost) {
        this.#host = host;
        this.#events = new VoiceCallSpeechSessionEventsController({
            isGenerationActive: (generation) => this.#active && this.#generation.isActive(generation),
            isActive: () => this.#active,
            setAssistantAudioActive: (active) => this.#setAssistantAudioActive(active),
            setAssistantSpeaking: (speaking) => this.#setAssistantSpeaking(speaking),
            onSegmentPlaybackStart: (text) => this.#host.onSegmentPlaybackStart(text),
            onPlaybackFailure: (error, generation) => this.#handleSessionError(error, generation),
            syncCompletion: () => this.#syncCompletion()
        });
    }

    start(): void {
        if (this.#active) {
            return;
        }
        this.#active = true;
        this.#paused = false;
    }

    resetForRequest(requestKey: string, settings: VoiceCallTtsSettings): void {
        this.#requestKey = requestKey;
        this.#settings = settings;
        this.#cancelPlayback({ clearSettings: false });
        this.#drainNotified = true;
    }

    stop(): void {
        if (!this.#active) {
            return;
        }
        this.#active = false;
        this.#paused = false;
        this.#cancelPlayback({ clearSettings: true });
        void this.#events.dispose().catch((error) => {
            errorHandler.warn('VoiceCallSpeechPlaybackController', 'Voice call speech scheduler disposal failed', ensureError(error));
        });
    }

    interrupt(): void {
        this.#cancelPlayback({ clearSettings: false });
    }

    pause(): void {
        if (!this.#active || this.#paused) {
            return;
        }
        this.#paused = true;
        this.#cancelPlayback({ clearSettings: false });
    }

    resume(): void {
        if (!this.#active || !this.#paused) {
            return;
        }
        this.#paused = false;
        this.#pump();
        this.#syncCompletion();
    }

    isAssistantAudioActive(): boolean {
        return this.#assistantAudioActive;
    }

    hasPendingSpeech(): boolean {
        return this.#session !== null || this.#sessionStarting || this.#sending || this.#queue.length > 0 || this.#events.hasPendingAudio();
    }

    enqueueSegments(segments: VoiceCallSpeechSegment[]): void {
        if (!this.#active || this.#paused || segments.length === 0 || this.#requestKey === null) {
            return;
        }
        for (const segment of segments) {
            if (segment.requestKey === this.#requestKey && segment.text.trim()) {
                this.#queue.push({ requestKey: segment.requestKey, segmentSequence: segment.segmentSequence, text: segment.text.trim() });
            }
        }
        if (this.#queue.length > 0) {
            this.#drainNotified = false;
        }
        this.#pump();
    }

    finishCurrentRequest(): void {
        if (!this.#active || this.#requestKey === null) {
            return;
        }
        if (this.#session === null && !this.#sessionStarting && this.#queue.length === 0) {
            this.#syncCompletion();
            return;
        }
        this.#finishRequested = true;
        this.#pump();
    }

    #cancelPlayback(options: { clearSettings: boolean }): void {
        this.#generation.invalidate();
        this.#sessionStarting = false;
        this.#sending = false;
        this.#finishRequested = false;
        this.#queue = [];
        this.#events.reset();
        const session = this.#session;
        this.#session = null;
        if (session !== null) {
            void session.cancel('Cancelled').catch((error) => {
                errorHandler.warn('VoiceCallSpeechPlaybackController', 'Voice call speech session cancellation failed', ensureError(error));
            });
        }
        if (options.clearSettings) {
            this.#settings = null;
            this.#requestKey = null;
        }
        this.#setAssistantSpeaking(false);
        this.#setAssistantAudioActive(false);
    }

    #pump(): void {
        if (!this.#active || this.#paused || this.#host.isUserSpeechConfirmed() || this.#sending || this.#sessionStarting) {
            return;
        }
        const settings = this.#settings;
        const requestKey = this.#requestKey;
        if (settings === null || requestKey === null) {
            this.#syncCompletion();
            return;
        }
        const generation = this.#generation.value;
        void this.#pumpAsync(requestKey, settings, generation).catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn('VoiceCallSpeechPlaybackController', 'Voice call speech session pump failed', runtimeError);
            this.#handleSessionError(runtimeError, generation);
        });
    }

    async #pumpAsync(requestKey: string, settings: VoiceCallTtsSettings, generation: number): Promise<void> {
        const session = await this.#ensureSession(settings, generation);
        if (session === null || !this.#canUseRequest(requestKey, generation)) {
            return;
        }
        this.#sending = true;
        try {
            while (this.#queue.length > 0 && this.#canUseRequest(requestKey, generation)) {
                const segment = this.#queue.shift();
                if (!segment || segment.requestKey !== requestKey || this.#events.hasStarted(segment.segmentSequence)) {
                    continue;
                }
                this.#events.rememberSegment(segment);
                await session.sendSegment(segment.segmentSequence, segment.text);
            }
            if (this.#finishRequested && this.#canUseRequest(requestKey, generation)) {
                this.#finishRequested = false;
                await session.finish();
            }
        } finally {
            if (this.#generation.isActive(generation)) {
                this.#sending = false;
            }
        }
        this.#syncCompletion();
    }

    async #ensureSession(settings: VoiceCallTtsSettings, generation: number): Promise<OpenAiAudioSpeechSessionClient | null> {
        if (this.#session !== null) {
            return this.#session;
        }
        if (this.#sessionStarting) {
            return null;
        }
        this.#sessionStarting = true;
        let session: OpenAiAudioSpeechSessionClient | null = null;
        try {
            session = await VoiceCallSpeechSessionConnectionController(
                settings,
                {
                    onStarted: () => {},
                    onSegmentStarted: () => {},
                    onChunk: (segmentSequence, chunkSequence, chunkBase64) => this.#events.handleChunk(segmentSequence, chunkSequence, chunkBase64, generation),
                    onSegmentCompleted: (segmentSequence) => this.#events.handleSegmentCompleted(segmentSequence, generation),
                    onCompleted: () => this.#handleSessionCompleted(generation),
                    onCancelled: () => this.#handleSessionCompleted(generation),
                    onError: (error) => this.#handleSessionError(error, generation)
                },
                (payload, callbacks) => this.#host.speechSessionFactory.create(payload, callbacks)
            );
            if (!this.#generation.isActive(generation)) {
                await session.cancel('Stale speech session');
                return null;
            }
            if (!session.isActive()) {
                return null;
            }
        } finally {
            if (this.#generation.isActive(generation)) {
                this.#sessionStarting = false;
            }
        }
        this.#session = session;
        return session;
    }

    #handleSessionCompleted(generation: number): void {
        if (!this.#generation.isActive(generation)) {
            return;
        }
        this.#session = null;
        this.#syncCompletion();
    }

    #handleSessionError(error: Error, generation: number): void {
        if (!this.#generation.isActive(generation)) {
            return;
        }
        this.#host.feedback.show(i18n.t('chat.voiceCall.ttsFailed'), 'error');
        this.#host.onPlaybackFailure(error);
        this.#cancelPlayback({ clearSettings: false });
    }

    #canUseRequest(requestKey: string, generation: number): boolean {
        return this.#active && !this.#paused && this.#requestKey === requestKey && this.#generation.isActive(generation);
    }

    #syncCompletion(): void {
        if (this.#paused || this.hasPendingSpeech()) {
            return;
        }
        this.#setAssistantSpeaking(false);
        this.#setAssistantAudioActive(false);
        if (!this.#drainNotified && this.#active) {
            this.#drainNotified = true;
            this.#host.onSpeechQueueDrained();
        }
    }

    #setAssistantAudioActive(active: boolean): void {
        if (this.#assistantAudioActive === active) {
            return;
        }
        this.#assistantAudioActive = active;
    }

    #setAssistantSpeaking(speaking: boolean): void {
        if (this.#assistantSpeaking === speaking) {
            return;
        }
        this.#assistantSpeaking = speaking;
        this.#host.onAssistantSpeechStateChange(speaking);
    }
}

export { VoiceCallSpeechPlaybackController };
