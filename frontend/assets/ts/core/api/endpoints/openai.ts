/* SoAI - Shared frontend API endpoint layer OpenAI [frontend/assets/ts/core/api/endpoints/openai.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeOpenAiModel, decodeOpenAiModelCatalog, type OpenAiModelCatalogEntry, type OpenAiModelCatalogResponse } from '@core/api/contracts/openAiModelCatalogContracts.ts';
import { decodeOpenAiChatResponse, decodeOpenAiCompletionResponse, decodeOpenAiEmbeddingResponse, decodeOpenAiImageResponse, decodeOpenAiTranscriptionResponse, type OpenAiChatCompletionResponse, type OpenAiCompletionResponse, type OpenAiEmbeddingResponse, type OpenAiImageResponse, type OpenAiTranscriptionResponse } from '@core/api/contracts/openAiResponseContracts.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import type { SnapshotRequestOptions } from '@core/websocketclient/types.ts';

interface OpenAiTransportOptions {
    signal?: AbortSignal | undefined;
    timeoutMs?: number | undefined;
}

const buildTransportOptions = (options: OpenAiTransportOptions): RequestOptions => ({
    ...(options.signal === undefined ? {} : { signal: options.signal }),
    ...(options.timeoutMs === undefined ? {} : { timeoutMs: options.timeoutMs })
});

const requireRawResponse = (value: ApiResponsePayload): Response => {
    if (!(value instanceof Response)) {
        throw new TypeError('OpenAI streaming request did not return a raw Response.');
    }
    return value;
};

const cloneTranscriptionFormData = (payload: FormData, stream: boolean): FormData => {
    const cloned = new FormData();
    for (const [field, value] of payload.entries()) {
        if (typeof value === 'string') {
            cloned.append(field, value);
        } else {
            cloned.append(field, value, value.name);
        }
    }
    cloned.set('stream', String(stream));
    return cloned;
};

const createOpenAIEndpoints = (api: ApiClientContext) => ({
    models: async (options: RequestOptions = {}): Promise<OpenAiModelCatalogResponse> => {
        const snapshotOptions: SnapshotRequestOptions = { retryOnReconnect: true };
        if (options.signal) snapshotOptions.signal = options.signal;
        if (options.timeoutMs !== undefined) snapshotOptions.timeoutMs = options.timeoutMs;
        return decodeOpenAiModelCatalog((await getWebSocketClient().requestSnapshot('openai.models', null, snapshotOptions)).data);
    },
    model: async (id: string): Promise<OpenAiModelCatalogEntry> => decodeOpenAiModel(await api.get(`/v1/models/${api.encodePathSegment(id)}`)),
    chat: {
        create: async (payload: JsonObject, options: OpenAiTransportOptions = {}): Promise<OpenAiChatCompletionResponse> => decodeOpenAiChatResponse(await api.post('/v1/chat/completions', { ...payload, stream: false }, buildTransportOptions(options))),
        stream: async (payload: JsonObject, options: OpenAiTransportOptions = {}): Promise<Response> => requireRawResponse(await api.post('/v1/chat/completions', { ...payload, stream: true }, { ...buildTransportOptions(options), rawResponse: true }))
    },
    completions: {
        create: async (payload: JsonObject, options: OpenAiTransportOptions = {}): Promise<OpenAiCompletionResponse> => decodeOpenAiCompletionResponse(await api.post('/v1/completions', { ...payload, stream: false }, buildTransportOptions(options))),
        stream: async (payload: JsonObject, options: OpenAiTransportOptions = {}): Promise<Response> => requireRawResponse(await api.post('/v1/completions', { ...payload, stream: true }, { ...buildTransportOptions(options), rawResponse: true }))
    },
    embeddings: async (payload: JsonObject, options: RequestOptions = {}): Promise<OpenAiEmbeddingResponse> => decodeOpenAiEmbeddingResponse(await api.post('/v1/embeddings', payload, options)),
    images: {
        generate: async (payload: JsonObject, options: OpenAiTransportOptions = {}): Promise<OpenAiImageResponse> => decodeOpenAiImageResponse(await api.post('/v1/images/generations', { ...payload, stream: false }, buildTransportOptions(options))),
        stream: async (payload: JsonObject, options: OpenAiTransportOptions = {}): Promise<Response> => requireRawResponse(await api.post('/v1/images/generations', { ...payload, stream: true }, { ...buildTransportOptions(options), rawResponse: true }))
    },
    audio: {
        transcriptions: {
            create: async (payload: FormData, options: OpenAiTransportOptions = {}): Promise<OpenAiTranscriptionResponse> => decodeOpenAiTranscriptionResponse(await api.post('/v1/audio/transcriptions', cloneTranscriptionFormData(payload, false), { headers: {}, ...buildTransportOptions(options) })),
            stream: async (payload: FormData, options: OpenAiTransportOptions = {}): Promise<Response> => requireRawResponse(await api.post('/v1/audio/transcriptions', cloneTranscriptionFormData(payload, true), { headers: {}, ...buildTransportOptions(options), rawResponse: true }))
        },
        speech: {
            create: async (payload: JsonObject, options: OpenAiTransportOptions = {}): Promise<Response> => requireRawResponse(await api.post('/v1/audio/speech', payload, { ...buildTransportOptions(options), rawResponse: true }))
        }
    }
});

export { createOpenAIEndpoints };
export type { OpenAiTransportOptions };
