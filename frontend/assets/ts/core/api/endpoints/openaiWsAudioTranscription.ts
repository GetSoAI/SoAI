/* SoAI - Shared frontend API endpoint layer OpenAI WebSocket audio transcription [frontend/assets/ts/core/api/endpoints/openaiWsAudioTranscription.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { appendTranscriptionStartFormFields, readTranscriptionAudioFile, readTranscriptionModel, readTranscriptionResponseFormat, validateWebuiTranscriptionFormData } from '@core/api/endpoints/openaiWsAudioTranscriptionForm.ts';
import { decodeOpenAiTranscriptionResponse, type OpenAiTranscriptionResponse } from '@core/api/contracts/openAiResponseContracts.ts';
import { APIError } from '@core/apiError.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { encodeBase64Bytes } from '@core/primitives/base64.ts';
import { secondsToMs } from '@core/time/durations.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { createWebSocketRunId, prepareWebSocketRun, type WebSocketRunCorrelation } from '@core/websocketclient/runCorrelation.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';

const CHUNK_SIZE_BYTES = 256 * 1024;
const TRANSCRIPTION_SETTLEMENT_TIMEOUT_MS = secondsToMs(15);
const TRANSCRIPTION_DEADLINE_EXCEEDED_CODE = 'transcription_deadline_exceeded';
const TRANSCRIPTION_CANCELLATION_UNCONFIRMED_CODE = 'transcription_cancellation_unconfirmed';

interface TranscriptionRequestOptions extends RequestOptions {
    onDeadlineSettlement?: (() => void) | undefined;
}

const serializeTranscriptionCancel = (runId: string, reason: string): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_TRANSCRIPTION_CANCEL,
    'run_id': runId,
    reason
});

const serializeTranscriptionStart = (inputArguments: { runId: string; originalFilename: string; model: string; responseFormat: string }): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_TRANSCRIPTION_START,
    'run_id': inputArguments.runId,
    'original_filename': inputArguments.originalFilename,
    model: inputArguments.model,
    'response_format': inputArguments.responseFormat
});

const serializeTranscriptionChunk = (runId: string, sequence: number, chunkBase64: string): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_TRANSCRIPTION_CHUNK,
    'run_id': runId,
    sequence,
    'chunk_base64': chunkBase64
});

const serializeTranscriptionCommit = (runId: string): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.OPENAI_AUDIO_TRANSCRIPTION_COMMIT,
    'run_id': runId
});

const transcribeAudioOverWebSocket = async (payload: FormData, options: TranscriptionRequestOptions = {}): Promise<OpenAiTranscriptionResponse> => {
    throwIfAborted(options.signal, 'Request aborted');
    validateWebuiTranscriptionFormData(payload);
    const audioFile = readTranscriptionAudioFile(payload);
    const model = readTranscriptionModel(payload);
    const responseFormat = readTranscriptionResponseFormat(payload);
    if (!audioFile) {
        throw new Error('Audio transcription requires a file');
    }
    if (!model) {
        throw new Error('Audio transcription requires a model');
    }
    const originalFilename = audioFile instanceof File && audioFile.name ? audioFile.name : 'audio';
    const runId = createWebSocketRunId('ws_openai_transcription');
    const ws = getWebSocketClient();
    let stopRequested = false;
    let stopError: Error | null = null;
    let settling = false;
    let taskId: string | null = null;
    const createSettlementError = (code: string, message: string): APIError => new APIError(0, message, taskId === null ? { code } : { code, taskId });
    const run = await prepareWebSocketRun<OpenAiTranscriptionResponse>({
        runId,
        acceptedTypes: [WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_TRANSCRIPTION_STARTED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_TRANSCRIPTION_COMPLETED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_TRANSCRIPTION_CANCELLED, WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_TRANSCRIPTION_ERROR],
        eventCancelled: WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_TRANSCRIPTION_CANCELLED,
        eventError: WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_TRANSCRIPTION_ERROR,
        requestOptions: options,
        deadlineSettlement: {
            timeoutMs: TRANSCRIPTION_SETTLEMENT_TIMEOUT_MS,
            onStart: () => {
                settling = true;
                options.onDeadlineSettlement?.();
            },
            createCancelledError: () => createSettlementError(TRANSCRIPTION_DEADLINE_EXCEEDED_CODE, 'Audio transcription exceeded its time limit and was cancelled'),
            createUnconfirmedError: () => createSettlementError(TRANSCRIPTION_CANCELLATION_UNCONFIRMED_CODE, 'Audio transcription cancellation was not confirmed')
        },
        onCancelSend: async () => ws.sendMessage(serializeTranscriptionCancel(runId, 'Cancelled'), { waitForConnection: false }),
        onMessage: (messagePayload, resolve, reject, eventType) => {
            if (!isJsonObject(messagePayload)) {
                reject(new Error('Invalid transcription response'));
                return;
            }
            if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_AUDIO_TRANSCRIPTION_STARTED) {
                taskId = toTrimmedString(messagePayload['task_id']) || null;
                return;
            }
            resolve(decodeOpenAiTranscriptionResponse(messagePayload['result']));
        }
    });
    void run.result.catch((error) => {
        stopRequested = true;
        stopError = ensureError(error);
    });
    try {
        await sendTranscriptionUpload({ payload, audioFile, model, responseFormat, originalFilename, runId, run, requestSignal: options.signal, settling: () => settling, stopRequested: () => stopRequested, stopError: () => stopError });
        return await run.result;
    } catch (error) {
        const runtimeError = ensureError(error);
        run.fail(runtimeError);
        await run.result.catch((settlementError) => {
            errorHandler.debug('OpenAIWsAudioTranscription', 'Transcription run settled during request failure cleanup', ensureError(settlementError));
        });
        throw runtimeError;
    }
};

const sendTranscriptionUpload = async (inputArguments: { payload: FormData; audioFile: Blob; model: string; responseFormat: string; originalFilename: string; runId: string; run: WebSocketRunCorrelation<OpenAiTranscriptionResponse>; requestSignal?: AbortSignal | undefined; settling(): boolean; stopRequested(): boolean; stopError(): Error | null }): Promise<void> => {
    throwIfAborted(inputArguments.requestSignal, 'Request aborted');
    const startMessage = serializeTranscriptionStart(inputArguments);
    appendTranscriptionStartFormFields(startMessage, inputArguments.payload);
    await inputArguments.run.send(startMessage);
    let sequence = 0;
    for (let offset = 0; offset < inputArguments.audioFile.size; offset += CHUNK_SIZE_BYTES) {
        if (inputArguments.settling()) return;
        if (inputArguments.stopRequested()) {
            throw inputArguments.stopError() || new Error('Audio transcription upload stopped');
        }
        throwIfAborted(inputArguments.requestSignal, 'Request aborted');
        const slice = inputArguments.audioFile.slice(offset, Math.min(offset + CHUNK_SIZE_BYTES, inputArguments.audioFile.size));
        const buffer = await slice.arrayBuffer();
        throwIfAborted(inputArguments.requestSignal, 'Request aborted');
        await inputArguments.run.send(serializeTranscriptionChunk(inputArguments.runId, sequence, encodeBase64Bytes(new Uint8Array(buffer))));
        sequence += 1;
    }
    if (inputArguments.settling()) return;
    if (inputArguments.stopRequested()) {
        throw inputArguments.stopError() || new Error('Audio transcription upload stopped');
    }
    throwIfAborted(inputArguments.requestSignal, 'Request aborted');
    await inputArguments.run.send(serializeTranscriptionCommit(inputArguments.runId));
};

export { TRANSCRIPTION_CANCELLATION_UNCONFIRMED_CODE, TRANSCRIPTION_DEADLINE_EXCEEDED_CODE, transcribeAudioOverWebSocket };
export type { TranscriptionRequestOptions };
