/* SoAI - Shared frontend API endpoint layer OpenAI WebSocket audio speech request [frontend/assets/ts/core/api/endpoints/openaiWsAudioSpeechRequest.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestOptions } from '@core/api/types/request.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { decodeBase64Bytes } from '@core/primitives/base64.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { createWebSocketRunId, prepareWebSocketRun } from '@core/websocketclient/runCorrelation.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';

const serializeSpeechRunMessage = (type: string, runId: string, reason: string): JsonObject => ({
    type,
    'run_id': runId,
    reason
});

const serializeSpeechStartMessage = (runId: string, payload: JsonObject): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_SPEECH_START,
    'run_id': runId,
    payload
});

const generateSpeechOverWebSocket = async (payload: JsonValue, options: RequestOptions = {}): Promise<Response> => {
    throwIfAborted(options.signal, 'Request aborted');
    const runId = createWebSocketRunId('ws_openai_speech');
    const requestPayload = isJsonObject(payload) ? payload : {};
    if ('stream_format' in requestPayload) {
        throw new Error('WebUI speech does not accept stream_format');
    }
    const ws = getWebSocketClient();
    const chunks: Uint8Array[] = [];
    let mediaType = 'audio/mpeg';
    let nextSequence = 0;
    const run = await prepareWebSocketRun<Response>({
        runId,
        acceptedTypes: [WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_STARTED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_CHUNK, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_COMPLETED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_CANCELLED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_ERROR],
        eventCancelled: WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_CANCELLED,
        eventError: WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_ERROR,
        requestOptions: options,
        onCancelSend: async () => ws.sendMessage(serializeSpeechRunMessage(WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_SPEECH_CANCEL, runId, 'Cancelled'), { waitForConnection: false }),
        onMessage: (messagePayload, resolve, reject) => {
            if (!isJsonObject(messagePayload)) {
                reject(new Error('Invalid speech response'));
                return;
            }
            const typeValue = messagePayload['type'];
            const type = isString(typeValue) ? typeValue : '';
            if (type === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_STARTED) {
                mediaType = readMediaType(messagePayload, mediaType);
                return;
            }
            if (type === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_CHUNK) {
                try {
                    nextSequence = appendSpeechChunk(chunks, messagePayload, nextSequence);
                } catch (error) {
                    reject(ensureError(error));
                }
                return;
            }
            if (type === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_SPEECH_COMPLETED) {
                const chunkCount = messagePayload['chunk_count'];
                if (!isNonNegativeInteger(chunkCount) || chunkCount !== nextSequence) {
                    reject(new Error('Speech chunk count does not match completion'));
                    return;
                }
                const byteLength = chunks.reduce((total, chunk) => total + chunk.byteLength, 0);
                const audioBytes = new Uint8Array(byteLength);
                let offset = 0;
                for (const chunk of chunks) {
                    audioBytes.set(chunk, offset);
                    offset += chunk.byteLength;
                }
                resolve(new Response(audioBytes, { headers: { 'content-type': mediaType } }));
            }
        }
    });
    try {
        throwIfAborted(options.signal, 'Request aborted');
        await run.send(serializeSpeechStartMessage(runId, requestPayload));
        return await run.result;
    } catch (error) {
        const runtimeError = ensureError(error);
        run.fail(runtimeError);
        await run.result.catch((settlementError) => {
            errorHandler.debug('OpenAIWsAudioSpeechRequest', 'Speech run settled during request failure cleanup', ensureError(settlementError));
        });
        throw runtimeError;
    }
};

const readMediaType = (messagePayload: JsonObject, fallback: string): string => {
    const mediaTypeValue = messagePayload['media_type'];
    return isString(mediaTypeValue) && mediaTypeValue.trim() ? mediaTypeValue.trim() : fallback;
};

const appendSpeechChunk = (chunks: Uint8Array[], messagePayload: JsonObject, expectedSequence: number): number => {
    const sequenceValue = messagePayload['sequence'];
    if (!isNonNegativeInteger(sequenceValue) || sequenceValue !== expectedSequence) {
        throw new Error('Speech chunk sequence is out of order');
    }
    const chunkBase64Value = messagePayload['chunk_base64'];
    if (!isString(chunkBase64Value) || !chunkBase64Value) {
        throw new Error('Speech chunk payload is invalid');
    }
    const bytes = decodeBase64Bytes(chunkBase64Value);
    if (bytes.byteLength === 0) {
        throw new Error('Speech chunk payload is invalid');
    }
    const copy = new Uint8Array(bytes.byteLength);
    copy.set(bytes);
    chunks.push(copy);
    return expectedSequence + 1;
};

export { generateSpeechOverWebSocket };
