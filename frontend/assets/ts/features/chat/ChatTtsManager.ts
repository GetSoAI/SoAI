/* SoAI - Chat feature TTS manager [frontend/assets/ts/features/chat/ChatTtsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { WebuiMediaApiClient } from '@features/chat/api/webuiMediaAudio.ts';
import { ChatTtsAudioCache, type PreparedChatTtsAudio } from '@features/chat/tts/chatTtsAudioCache.ts';
import { fetchOpenAiAudioUrl, type OpenAiSpeechPayload, type TtsResponseFormat } from '@features/chat/tts/chatTtsOpenAiAudio.ts';
import { splitTextForTts } from '@features/chat/tts/chatTtsTextChunker.ts';

const DEFAULT_CACHE_LIMIT = 16;
const TTS_CHUNK_MAX_CHARS = 4000;
const SILENT_WAV_DATA_URI = 'data:audio/wav;base64,UklGRsQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YaAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA';

class ChatTtsManager {
    readonly #apiClient: WebuiMediaApiClient | null;
    #audio: HTMLAudioElement;
    #cache: ChatTtsAudioCache;
    #currentAbort: AbortController | null;
    #playbackPrimed: boolean;
    #playbackPrimeInFlight: boolean;
    #playbackPrimeMutedRestore: boolean | null;
    readonly #speakToken = new SequenceToken();

    constructor(options: { apiClient: WebuiMediaApiClient | null; cacheLimit?: number }) {
        this.#apiClient = options.apiClient;
        this.#audio = new Audio();
        this.#audio.preload = 'auto';
        const cacheLimitCandidate = options.cacheLimit;
        const cacheLimit = typeof cacheLimitCandidate === 'number' && Number.isInteger(cacheLimitCandidate) && cacheLimitCandidate > 0 ? cacheLimitCandidate : DEFAULT_CACHE_LIMIT;
        this.#cache = new ChatTtsAudioCache(cacheLimit);
        this.#currentAbort = null;
        this.#playbackPrimed = false;
        this.#playbackPrimeInFlight = false;
        this.#playbackPrimeMutedRestore = null;
    }
    primePlayback(): void {
        if (this.#playbackPrimed || this.#playbackPrimeInFlight) {
            return;
        }
        this.#playbackPrimeInFlight = true;
        const token = this.#speakToken.value;
        const previousMuted = this.#audio.muted;
        this.#playbackPrimeMutedRestore = previousMuted;
        this.#audio.muted = true;
        this.#audio.src = SILENT_WAV_DATA_URI;
        this.#audio.currentTime = 0;
        this.#audio
            .play()
            .then(() => {
                this.#playbackPrimed = true;
                if (this.#speakToken.isActive(token)) {
                    this.#audio.pause();
                    this.#audio.removeAttribute('src');
                    this.#audio.load();
                }
            })
            .catch((error) => {
                errorHandler.debug('ChatTtsManager', 'Silent playback prime failed', ensureError(error));
            })
            .finally(() => {
                this.#finishPlaybackPrime(token);
            });
    }
    #finishPlaybackPrime(token: number): void {
        if (!this.#speakToken.isActive(token)) {
            return;
        }
        this.#playbackPrimeInFlight = false;
        this.#restorePlaybackPrimeMute();
    }
    #restorePlaybackPrimeMute(): void {
        const restoreMuted = this.#playbackPrimeMutedRestore;
        this.#playbackPrimeMutedRestore = null;
        if (restoreMuted === null) {
            return;
        }
        this.#audio.muted = restoreMuted;
    }
    stop(): void {
        this.#restorePlaybackPrimeMute();
        this.#playbackPrimeInFlight = false;
        this.#speakToken.invalidate();
        this.#currentAbort?.abort();
        this.#currentAbort = null;
        this.#audio.pause();
        this.#audio.removeAttribute('src');
        this.#audio.load();
    }
    dispose(): void {
        this.stop();
        this.#cache.dispose();
    }
    #playUrl(url: string, signal: AbortSignal, options: { onPlaybackStart?: (() => void) | null } = {}): Promise<void> {
        const deferred = createDeferred<void>();
        const expectedSpeakToken = this.#speakToken.value;
        let settled = false;
        let started = false;
        const onPlaybackStart = options.onPlaybackStart ?? null;
        const notifyStartedIfValid = (): void => {
            if (settled || started || signal.aborted || !this.#speakToken.isActive(expectedSpeakToken)) {
                return;
            }
            started = true;
            this.#playbackPrimed = true;
            this.#audio.removeEventListener('playing', onPlaying);
            this.#audio.removeEventListener('timeupdate', onTimeUpdate);
            if (!onPlaybackStart) {
                return;
            }
            try {
                onPlaybackStart();
            } catch (error) {
                errorHandler.debug('ChatTtsManager', 'Failed to invoke playback start callback', ensureError(error));
            }
        };
        const finalize = (handler: () => void): void => {
            if (settled) {
                return;
            }
            settled = true;
            this.#audio.removeEventListener('ended', onEnded);
            this.#audio.removeEventListener('error', onError);
            this.#audio.removeEventListener('playing', onPlaying);
            this.#audio.removeEventListener('timeupdate', onTimeUpdate);
            signal.removeEventListener('abort', onAbort);
            handler();
        };
        const onEnded = (): void => finalize(() => deferred.resolve());
        const onAbort = (): void => finalize(() => deferred.resolve());
        const onError = (): void => finalize(() => deferred.reject(new Error('Audio playback failed')));
        const onPlaying = (): void => notifyStartedIfValid();
        const onTimeUpdate = (): void => {
            if (this.#audio.currentTime > 0) {
                notifyStartedIfValid();
            }
        };

        this.#audio.addEventListener('ended', onEnded);
        this.#audio.addEventListener('error', onError);
        this.#audio.addEventListener('playing', onPlaying);
        this.#audio.addEventListener('timeupdate', onTimeUpdate);
        signal.addEventListener('abort', onAbort);
        if (signal.aborted || !this.#speakToken.isActive(expectedSpeakToken)) {
            finalize(() => deferred.resolve());
            return deferred.promise;
        }

        this.#audio.src = url;
        this.#audio.currentTime = 0;
        this.#audio.play().catch((error) => {
            const runtimeError = ensureError(error);
            finalize(() => deferred.reject(runtimeError));
        });
        return deferred.promise;
    }
    async speakText(text: string, options: { model: string; voice?: string | null; speed?: number; responseFormat?: TtsResponseFormat; onPlaybackStart?: (() => void) | null }): Promise<void> {
        const normalized = toTrimmedString(text);
        if (!normalized) {
            return;
        }
        const model = toTrimmedString(options.model);
        if (!model) {
            throw new Error('ChatTtsManager requires a model id');
        }
        const voiceCandidate = options.voice;
        const voice = optionalTrimmedString(voiceCandidate);
        const speedCandidate = options.speed;
        const speed = typeof speedCandidate === 'number' && Number.isFinite(speedCandidate) && speedCandidate > 0 ? speedCandidate : 1;
        const responseFormat: TtsResponseFormat = options.responseFormat ?? 'wav';

        this.stop();
        const token = this.#speakToken.value;
        const abortController = new AbortController();
        this.#currentAbort = abortController;

        const chunks = splitTextForTts(normalized, { chunkMaxChars: TTS_CHUNK_MAX_CHARS });
        for (let index = 0; index < chunks.length; index += 1) {
            if (abortController.signal.aborted || !this.#speakToken.isActive(token)) {
                return;
            }
            const chunk = chunks[index];
            if (!chunk) {
                throw new Error('Text-to-speech chunk resolution failed.');
            }
            const payload: OpenAiSpeechPayload = voice ? { model, input: chunk, voice, responseFormat, speed } : { model, input: chunk, responseFormat, speed };
            const existing = this.#cache.retain(payload);
            if (existing) {
                try {
                    if (index === 0) {
                        await this.#playPreparedSpeech(existing, { signal: abortController.signal, onPlaybackStart: options.onPlaybackStart ?? null });
                    } else {
                        await this.#playPreparedSpeech(existing, { signal: abortController.signal });
                    }
                } finally {
                    existing.release();
                }
                continue;
            }
            let url: string | null = null;
            try {
                url = await fetchOpenAiAudioUrl(this.#apiClient, payload, abortController.signal);
            } catch (error) {
                if (abortController.signal.aborted) {
                    return;
                }
                throw error;
            }
            if (!url) {
                throw new Error('Text-to-speech request returned no audio');
            }
            if (abortController.signal.aborted || !this.#speakToken.isActive(token)) {
                URL.revokeObjectURL(url);
                return;
            }
            const prepared = this.#cache.storeAndRetain(payload, url);
            try {
                if (index === 0) {
                    await this.#playPreparedSpeech(prepared, { signal: abortController.signal, onPlaybackStart: options.onPlaybackStart ?? null });
                } else {
                    await this.#playPreparedSpeech(prepared, { signal: abortController.signal });
                }
            } catch (error) {
                if (abortController.signal.aborted) {
                    return;
                }
                throw error;
            } finally {
                prepared.release();
            }
        }
    }

    async #playPreparedSpeech(prepared: PreparedChatTtsAudio, options: { signal: AbortSignal; onPlaybackStart?: (() => void) | null }): Promise<void> {
        await this.#playUrl(prepared.url, options.signal, { onPlaybackStart: options.onPlaybackStart ?? null });
    }
}
export { ChatTtsManager };
