/* SoAI - Shared frontend API endpoint layer OpenAI WebSocket audio speech session [frontend/assets/ts/core/api/endpoints/openaiWsAudioSpeechSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { createAbortError, createAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { decodeBase64Bytes } from '@core/primitives/base64.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { createWebSocketRunCorrelation, createWebSocketRunId, type WebSocketRunCorrelation } from '@core/websocketclient/runCorrelation.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';

interface OpenAiAudioSpeechSessionPayload {
    model: string;
    voice?: string;
    speed?: number;
    responseFormat: 'wav';
}

interface OpenAiAudioSpeechSessionCallbacks {
    onStarted(mediaType: string): void;
    onSegmentStarted(segmentSequence: number): void;
    onChunk(segmentSequence: number, chunkSequence: number, chunkBase64: string): void;
    onSegmentCompleted(segmentSequence: number, chunkCount: number): void;
    onCompleted(): void;
    onCancelled(reason: string): void;
    onError(error: Error): void;
}

type SpeechSessionOutcome = { type: 'completed' } | { type: 'cancelled'; reason: string };

const serializeSpeechSessionPayload = (payload: OpenAiAudioSpeechSessionPayload): JsonObject => {
    const serialized: JsonObject = { model: payload.model, 'response_format': payload.responseFormat };
    if (payload.voice !== undefined) serialized['voice'] = payload.voice;
    if (payload.speed !== undefined) serialized['speed'] = payload.speed;
    return serialized;
};

const serializeSpeechSessionStart = (runId: string, payload: OpenAiAudioSpeechSessionPayload): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_SPEECH_SESSION_START,
    'run_id': runId,
    payload: serializeSpeechSessionPayload(payload)
});

const serializeSpeechSessionSegment = (runId: string, segmentSequence: number, input: string): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_SPEECH_SESSION_SEGMENT,
    'run_id': runId,
    'segment_sequence': segmentSequence,
    input
});

const serializeSpeechSessionTerminal = (type: string, runId: string, reason?: string): JsonObject => {
    const serialized: JsonObject = { type, 'run_id': runId };
    if (reason !== undefined) serialized['reason'] = reason;
    return serialized;
};

class OpenAiAudioSpeechSessionClient {
    readonly #payload: OpenAiAudioSpeechSessionPayload;
    readonly #callbacks: OpenAiAudioSpeechSessionCallbacks;
    readonly #nextChunkSequenceBySegment = new Map<number, number>();
    readonly #completedSegments = new Set<number>();
    #runId = '';
    #run: WebSocketRunCorrelation<SpeechSessionOutcome> | null = null;
    #startupAbortController: AbortController | null = null;
    #active = false;
    #finished = false;
    #failureReported = false;
    #suppressTerminalCallback = false;
    #cancelReason = 'Cancelled';

    constructor(payload: OpenAiAudioSpeechSessionPayload, callbacks: OpenAiAudioSpeechSessionCallbacks) {
        this.#payload = payload;
        this.#callbacks = callbacks;
    }

    async start(signal?: AbortSignal | null): Promise<void> {
        if (this.#active) return;
        const ws = getWebSocketClient();
        const startupAbortController = new AbortController();
        const startupSignalScope = createAbortSignalScope([signal, startupAbortController.signal]);
        this.#runId = createWebSocketRunId('ws_openai_speech_session');
        this.#startupAbortController = startupAbortController;
        this.#active = true;
        this.#finished = false;
        this.#failureReported = false;
        this.#suppressTerminalCallback = false;
        try {
            ws.connect();
            try {
                await ws.waitForConnection(undefined, { signal: startupSignalScope.signal });
            } finally {
                startupSignalScope.cleanup();
            }
            throwIfAborted(startupSignalScope.signal, 'Speech session aborted');
            if (!ws.isConnected()) throw new Error('WebSocket not connected');
            const run = createWebSocketRunCorrelation<SpeechSessionOutcome>({
                runId: this.#runId,
                acceptedTypes: [WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_STARTED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_STARTED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_CHUNK, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_COMPLETED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_COMPLETED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_CANCELLED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_ERROR],
                eventCancelled: '',
                eventError: WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_ERROR,
                signal: signal ?? undefined,
                connectionEpoch: ws.connectionEpoch,
                client: ws,
                onCancelSend: async () => ws.sendMessage(serializeSpeechSessionTerminal(WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_SPEECH_SESSION_CANCEL, this.#runId, this.#cancelReason), { waitForConnection: false }),
                onMessage: (eventPayload, resolve, reject) => this.#handleEvent(eventPayload, resolve, reject)
            });
            this.#run = run;
            this.#observeRun(run);
            await run.send(serializeSpeechSessionStart(this.#runId, this.#payload));
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#run) {
                this.#run.fail(runtimeError);
                await this.#run.result.catch((settlementError) => {
                    errorHandler.debug('OpenAiAudioSpeechSessionClient', 'Speech session settled during start failure cleanup', ensureError(settlementError));
                });
            } else {
                this.#deactivate();
                if (!this.#suppressTerminalCallback) this.#reportFailure(runtimeError);
            }
            throw runtimeError;
        } finally {
            startupSignalScope.cleanup();
            if (this.#startupAbortController === startupAbortController) this.#startupAbortController = null;
        }
    }

    isActive(): boolean {
        return this.#active;
    }

    async sendSegment(segmentSequence: number, input: string): Promise<void> {
        if (!this.#active || this.#finished || !this.#run) return;
        const normalized = input.trim();
        if (!normalized) return;
        await this.#run.send(serializeSpeechSessionSegment(this.#runId, segmentSequence, normalized));
    }

    async finish(): Promise<void> {
        if (!this.#active || this.#finished || !this.#run) return;
        this.#finished = true;
        await this.#run.send(serializeSpeechSessionTerminal(WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_SPEECH_SESSION_FINISH, this.#runId));
    }

    async cancel(reason: string): Promise<void> {
        this.#startupAbortController?.abort();
        if (!this.#active || !this.#run) {
            this.#suppressTerminalCallback = true;
            this.#deactivate();
            return;
        }
        this.#cancelReason = reason;
        this.#suppressTerminalCallback = true;
        this.#run.cancel(createAbortError('Speech session cancelled'));
        await this.#run.result.catch((error) => {
            errorHandler.debug('OpenAiAudioSpeechSessionClient', 'Speech session cancellation settled', ensureError(error));
        });
        this.#deactivate();
    }

    dispose(): void {
        this.#startupAbortController?.abort();
        if (this.#run) {
            this.#suppressTerminalCallback = true;
            this.#run.fail(createAbortError('Speech session disposed'), false);
        }
        this.#deactivate();
    }

    #observeRun(run: WebSocketRunCorrelation<SpeechSessionOutcome>): void {
        void run.result.then(
            (outcome) => {
                if (!this.#active || this.#run !== run) return;
                this.#deactivate();
                if (this.#suppressTerminalCallback) return;
                if (outcome.type === 'completed') this.#callbacks.onCompleted();
                else this.#callbacks.onCancelled(outcome.reason);
            },
            (error) => {
                if (this.#run !== run) return;
                this.#deactivate();
                if (!this.#suppressTerminalCallback) this.#reportFailure(ensureError(error));
            }
        );
    }

    #handleEvent(eventPayload: JsonValue, resolve: (outcome: SpeechSessionOutcome) => void, reject: (error: Error) => void): void {
        if (!isJsonObject(eventPayload)) {
            reject(new Error('Invalid speech session response'));
            return;
        }
        const eventType = eventPayload['type'];
        if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_STARTED) {
            this.#callbacks.onStarted(this.#readString(eventPayload, 'media_type', 'audio/wav'));
            return;
        }
        if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_STARTED) {
            const segmentSequence = this.#requireSequence(eventPayload, 'segment_sequence');
            if (this.#nextChunkSequenceBySegment.has(segmentSequence) || this.#completedSegments.has(segmentSequence)) throw new Error('Speech session segment started more than once');
            this.#nextChunkSequenceBySegment.set(segmentSequence, 0);
            this.#callbacks.onSegmentStarted(segmentSequence);
            return;
        }
        if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_CHUNK) {
            this.#handleChunk(eventPayload);
            return;
        }
        if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_SEGMENT_COMPLETED) {
            this.#handleSegmentCompleted(eventPayload);
            return;
        }
        if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_COMPLETED) {
            if (this.#nextChunkSequenceBySegment.size !== 0) throw new Error('Speech session completed with unfinished segments');
            resolve({ type: 'completed' });
            return;
        }
        if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_SESSION_CANCELLED) {
            resolve({ type: 'cancelled', reason: this.#readString(eventPayload, 'reason', 'Cancelled') });
        }
    }

    #handleChunk(payload: JsonObject): void {
        const segmentSequence = this.#requireSequence(payload, 'segment_sequence');
        const chunkSequence = this.#requireSequence(payload, 'chunk_sequence');
        if (this.#completedSegments.has(segmentSequence)) throw new Error('Speech session chunk arrived after segment completion');
        const expectedSequence = this.#nextChunkSequenceBySegment.get(segmentSequence) ?? 0;
        if (chunkSequence !== expectedSequence) throw new Error('Speech session chunk sequence is out of order');
        const chunkBase64 = payload['chunk_base64'];
        if (!isString(chunkBase64) || !chunkBase64) throw new Error('Speech session chunk payload is invalid');
        if (decodeBase64Bytes(chunkBase64).byteLength === 0) throw new Error('Speech session chunk payload is invalid');
        this.#nextChunkSequenceBySegment.set(segmentSequence, expectedSequence + 1);
        this.#callbacks.onChunk(segmentSequence, chunkSequence, chunkBase64);
    }

    #handleSegmentCompleted(payload: JsonObject): void {
        const segmentSequence = this.#requireSequence(payload, 'segment_sequence');
        const chunkCount = this.#requireSequence(payload, 'chunk_count');
        if (this.#completedSegments.has(segmentSequence)) throw new Error('Speech session segment completed more than once');
        const acceptedChunkCount = this.#nextChunkSequenceBySegment.get(segmentSequence) ?? 0;
        if (chunkCount !== acceptedChunkCount) throw new Error('Speech session chunk count does not match completion');
        this.#nextChunkSequenceBySegment.delete(segmentSequence);
        this.#completedSegments.add(segmentSequence);
        this.#callbacks.onSegmentCompleted(segmentSequence, chunkCount);
    }

    #requireSequence(payload: JsonObject, key: string): number {
        const value = payload[key];
        if (!isNonNegativeInteger(value)) throw new Error(`Speech session ${key} is invalid`);
        return value;
    }

    #readString(payload: JsonObject, key: string, fallback: string): string {
        const value = payload[key];
        return isString(value) && value.trim() ? value.trim() : fallback;
    }

    #reportFailure(error: Error): void {
        if (this.#failureReported) return;
        this.#failureReported = true;
        this.#callbacks.onError(error);
    }

    #deactivate(): void {
        this.#active = false;
        this.#run = null;
        this.#startupAbortController = null;
        this.#nextChunkSequenceBySegment.clear();
        this.#completedSegments.clear();
    }
}

export { OpenAiAudioSpeechSessionClient };
export type { OpenAiAudioSpeechSessionCallbacks, OpenAiAudioSpeechSessionPayload };
