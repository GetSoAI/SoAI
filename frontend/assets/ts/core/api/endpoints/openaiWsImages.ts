/* SoAI - Shared API OpenAI WebSocket images [frontend/assets/ts/core/api/endpoints/openaiWsImages.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeOpenAiImageResponse, type OpenAiImageResponse } from '@core/api/contracts/openAiResponseContracts.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { createWebSocketRunId, prepareWebSocketRun } from '@core/websocketclient/runCorrelation.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';

const serializeImageGenerationStart = (runId: string, payload: JsonObject): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.OPENAI_IMAGES_GENERATION_START,
    'run_id': runId,
    payload
});

const serializeImageGenerationCancel = (runId: string): JsonObject => ({
    type: WEBSOCKET_MESSAGE_TYPES.OPENAI_IMAGES_GENERATION_CANCEL,
    'run_id': runId,
    reason: 'Cancelled'
});

type WebuiImageGenerationResult = OpenAiImageResponse | Response;

const generateStreamingImages = async (runId: string, requestPayload: JsonObject, options: RequestOptions): Promise<Response> => {
    const ws = getWebSocketClient();
    const encoder = new TextEncoder();
    let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
    let bodyCancelled = false;
    let nextSequence = 0;
    let responseContentType: string | null = null;
    const started = createDeferred<string>();
    const run = await prepareWebSocketRun<void>({
        runId,
        acceptedTypes: [WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_STARTED, WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_STREAM_CHUNK, WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_COMPLETED, WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_CANCELLED, WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_ERROR],
        eventCancelled: WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_CANCELLED,
        eventError: WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_ERROR,
        requestOptions: options,
        onCancelSend: async () => ws.sendMessage(serializeImageGenerationCancel(runId), { waitForConnection: false }),
        onMessage: (eventPayload, resolve, reject) => {
            if (!isJsonObject(eventPayload) || controller === null) {
                reject(new Error('Invalid image stream response'));
                return;
            }
            const eventType = eventPayload['type'];
            if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_STARTED) {
                const contentType = eventPayload['content_type'];
                if (responseContentType !== null || !isString(contentType) || !contentType.trim()) {
                    reject(new Error('Image stream content type is invalid'));
                    return;
                }
                responseContentType = contentType.trim();
                started.resolve(responseContentType);
                return;
            }
            if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_STREAM_CHUNK) {
                const sequence = eventPayload['sequence'];
                const chunk = eventPayload['chunk'];
                if (!isNonNegativeInteger(sequence) || sequence !== nextSequence) {
                    reject(new Error('Image stream chunk sequence is out of order'));
                    return;
                }
                if (!isString(chunk) || !chunk) {
                    reject(new Error('Image stream chunk payload is invalid'));
                    return;
                }
                controller.enqueue(encoder.encode(chunk));
                nextSequence += 1;
                return;
            }
            if (eventType === WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_COMPLETED) {
                if (responseContentType === null) {
                    reject(new Error('Image stream completed before start metadata'));
                    return;
                }
                const chunkCount = eventPayload['chunk_count'];
                if (!isNonNegativeInteger(chunkCount) || chunkCount !== nextSequence) {
                    reject(new Error('Image stream chunk count does not match completion'));
                    return;
                }
                resolve();
            }
        }
    });
    const stream = new ReadableStream<Uint8Array>({
        start: (streamController): void => {
            controller = streamController;
        },
        cancel: (): void => {
            bodyCancelled = true;
            run.cancel(createAbortError('Image stream response body cancelled'));
        }
    });
    void run.result.then(
        () => controller?.close(),
        (error) => {
            if (!bodyCancelled) controller?.error(ensureError(error));
        }
    );
    void run.result.catch((error) => started.reject(ensureError(error)));
    try {
        await run.send(serializeImageGenerationStart(runId, requestPayload));
    } catch (error) {
        const runtimeError = ensureError(error);
        run.fail(runtimeError);
        await run.result.catch((settlementError) => {
            errorHandler.debug('OpenAIImages', 'Image stream settled during start failure cleanup', ensureError(settlementError));
        });
        throw runtimeError;
    }
    const contentType = await started.promise;
    return new Response(stream, {
        headers: {
            'cache-control': 'no-cache',
            'content-type': contentType
        }
    });
};

const generateBlockingImages = async (runId: string, requestPayload: JsonObject, options: RequestOptions): Promise<OpenAiImageResponse> => {
    const ws = getWebSocketClient();
    const run = await prepareWebSocketRun<OpenAiImageResponse>({
        runId,
        acceptedTypes: [WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_COMPLETED, WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_CANCELLED, WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_ERROR],
        eventCancelled: WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_CANCELLED,
        eventError: WEBSOCKET_EVENT_TYPES.OPENAI_IMAGES_GENERATION_ERROR,
        requestOptions: options,
        onCancelSend: async () => ws.sendMessage(serializeImageGenerationCancel(runId), { waitForConnection: false }),
        onMessage: (messagePayload, resolve, reject) => {
            if (!isJsonObject(messagePayload)) {
                reject(new Error('Invalid images response'));
                return;
            }
            const chunkCount = messagePayload['chunk_count'];
            if (!isNonNegativeInteger(chunkCount) || chunkCount !== 0) {
                reject(new Error('Blocking image response chunk count is invalid'));
                return;
            }
            const result = messagePayload['result'];
            if (result === undefined) {
                reject(new Error('Image generation did not return a result payload'));
                return;
            }
            resolve(decodeOpenAiImageResponse(result));
        }
    });
    try {
        await run.send(serializeImageGenerationStart(runId, requestPayload));
        return await run.result;
    } catch (error) {
        const runtimeError = ensureError(error);
        run.fail(runtimeError);
        await run.result.catch((settlementError) => {
            errorHandler.debug('OpenAIImages', 'Image run settled during request failure cleanup', ensureError(settlementError));
        });
        throw runtimeError;
    }
};

const generateImagesOverWebSocket = async (payload: JsonValue, options: RequestOptions = {}): Promise<WebuiImageGenerationResult> => {
    throwIfAborted(options.signal, 'Request aborted');
    const runId = createWebSocketRunId('ws_openai_images');
    const requestPayload = isJsonObject(payload) ? payload : {};
    if (requestPayload['stream'] === true) return generateStreamingImages(runId, requestPayload, options);
    return generateBlockingImages(runId, requestPayload, options);
};

export { generateImagesOverWebSocket };
export type { WebuiImageGenerationResult };
