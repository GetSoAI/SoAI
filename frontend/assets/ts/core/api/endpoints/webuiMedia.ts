/* SoAI - Frontend internal WebUI media transport [frontend/assets/ts/core/api/endpoints/webuiMedia.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpenAiImageResponse, OpenAiTranscriptionResponse } from '@core/api/contracts/openAiResponseContracts.ts';
import { generateSpeechOverWebSocket } from '@core/api/endpoints/openaiWsAudioSpeechRequest.ts';
import { OpenAiAudioSpeechSessionClient, type OpenAiAudioSpeechSessionCallbacks, type OpenAiAudioSpeechSessionPayload } from '@core/api/endpoints/openaiWsAudioSpeechSession.ts';
import { transcribeAudioOverWebSocket } from '@core/api/endpoints/openaiWsAudioTranscription.ts';
import { generateImagesOverWebSocket } from '@core/api/endpoints/openaiWsImages.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface WebuiMediaTransportOptions {
    signal?: AbortSignal | undefined;
    timeoutMs?: number | undefined;
}

const buildWebuiMediaRequestOptions = (options: WebuiMediaTransportOptions): RequestOptions => ({
    ...(options.signal === undefined ? {} : { signal: options.signal }),
    ...(options.timeoutMs === undefined ? {} : { timeoutMs: options.timeoutMs })
});

const createWebuiMediaEndpoints = () => ({
    images: {
        generate: async (payload: JsonObject, options: WebuiMediaTransportOptions = {}): Promise<OpenAiImageResponse | Response> => generateImagesOverWebSocket(payload, buildWebuiMediaRequestOptions(options))
    },
    audio: {
        transcriptions: {
            create: async (payload: FormData, options: WebuiMediaTransportOptions = {}): Promise<OpenAiTranscriptionResponse> => transcribeAudioOverWebSocket(payload, buildWebuiMediaRequestOptions(options))
        },
        speech: {
            create: async (payload: JsonObject, options: WebuiMediaTransportOptions = {}): Promise<Response> => generateSpeechOverWebSocket(payload, buildWebuiMediaRequestOptions(options)),
            session: {
                create: async (payload: OpenAiAudioSpeechSessionPayload, callbacks: OpenAiAudioSpeechSessionCallbacks): Promise<OpenAiAudioSpeechSessionClient> => {
                    return new OpenAiAudioSpeechSessionClient(payload, callbacks);
                }
            }
        }
    }
});

export { createWebuiMediaEndpoints };
export type { WebuiMediaTransportOptions };
