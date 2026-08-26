/* SoAI - WebUI media audio helpers for chat features [frontend/assets/ts/features/chat/api/webuiMediaAudio.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpenAiTranscriptionResponse } from '@core/api/contracts/openAiResponseContracts.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

interface WebuiTranscriptionsApi {
    create(payload: FormData, options?: RequestOptions): Promise<OpenAiTranscriptionResponse>;
}

interface WebuiSpeechApi {
    create(payload: JsonObject, options?: RequestOptions): Promise<Response>;
}

interface WebuiMediaApiClient {
    webui?: {
        media?: {
            audio?: {
                transcriptions?: {
                    create?: CallableFunction | null | undefined;
                } | null;
                speech?: {
                    create?: CallableFunction | null | undefined;
                } | null;
            } | null;
        } | null;
    } | null;
}

type RecordingExtension = 'webm' | 'ogg' | 'm4a' | 'wav';

interface TranscribeAudioBlobArguments {
    apiClient: WebuiMediaApiClient | null;
    blob: Blob;
    mimeType: string;
    filenameStem: string;
    model: string;
    signal?: AbortSignal | undefined;
    context: string;
}

const RECORDING_MIME_TYPES: readonly string[] = Object.freeze(['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4', 'audio/wav']);

type WebuiTranscriptionMethod = (payload: FormData, options?: RequestOptions) => Promise<OpenAiTranscriptionResponse>;
type WebuiSpeechMethod = (payload: JsonObject, options?: RequestOptions) => Promise<Response>;

const isWebuiTranscriptionMethod = (value: CallableFunction | null | undefined): value is WebuiTranscriptionMethod => {
    return isFunction(value);
};

const isWebuiSpeechMethod = (value: CallableFunction | null | undefined): value is WebuiSpeechMethod => {
    return isFunction(value);
};

const resolveWebuiAudio = (apiClient: WebuiMediaApiClient | null, context: string): { transcriptionCreate?: CallableFunction | null | undefined; speechCreate?: CallableFunction | null | undefined } => {
    if (!apiClient) {
        throw new Error(`${context} requires core.apiClient.webui.media.audio`);
    }
    const webui = apiClient.webui;
    if (!isObject(webui) || !isObject(webui.media)) {
        throw new Error(`${context} requires core.apiClient.webui.media.audio`);
    }
    const audio = webui.media.audio;
    if (!isObject(audio)) {
        throw new Error(`${context} requires core.apiClient.webui.media.audio`);
    }
    return {
        transcriptionCreate: isObject(audio.transcriptions) ? audio.transcriptions.create : undefined,
        speechCreate: isObject(audio.speech) ? audio.speech.create : undefined
    };
};

const requireWebuiTranscriptionsApi = (apiClient: WebuiMediaApiClient | null, context: string): WebuiTranscriptionsApi => {
    const audio = resolveWebuiAudio(apiClient, context);
    const create = audio.transcriptionCreate;
    if (!isWebuiTranscriptionMethod(create)) {
        throw new Error(`${context} requires core.apiClient.webui.media.audio.transcriptions.create`);
    }
    return {
        create: (payload: FormData, options?: RequestOptions): Promise<OpenAiTranscriptionResponse> => create(payload, options)
    };
};

const requireWebuiSpeechApi = (apiClient: WebuiMediaApiClient | null, context: string): WebuiSpeechApi => {
    const audio = resolveWebuiAudio(apiClient, context);
    const create = audio.speechCreate;
    if (!isWebuiSpeechMethod(create)) {
        throw new Error(`${context} requires core.apiClient.webui.media.audio.speech.create`);
    }
    return {
        create: (payload: JsonObject, options?: RequestOptions): Promise<Response> => create(payload, options)
    };
};

const resolveRecordingFileExtension = (mimeType: string): RecordingExtension => {
    const normalized = mimeType.toLowerCase();
    if (normalized.includes('webm')) return 'webm';
    if (normalized.includes('ogg')) return 'ogg';
    if (normalized.includes('mp4')) return 'm4a';
    if (normalized.includes('wav')) return 'wav';
    throw new Error(`Unsupported recording mime type: ${mimeType}`);
};

const resolveSupportedRecordingMimeType = (): string => {
    if (typeof MediaRecorder !== 'function' || !isFunction(MediaRecorder.isTypeSupported)) {
        throw new Error('MediaRecorder API not supported');
    }
    for (const mimeType of RECORDING_MIME_TYPES) {
        if (MediaRecorder.isTypeSupported(mimeType)) {
            return mimeType;
        }
    }
    throw new Error('No supported audio mime type available');
};

const transcribeAudioBlob = async (inputArguments: TranscribeAudioBlobArguments): Promise<string> => {
    const extension = resolveRecordingFileExtension(inputArguments.mimeType);
    const formData = new FormData();
    formData.append('file', inputArguments.blob, `${inputArguments.filenameStem}.${extension}`);
    formData.append('model', inputArguments.model);
    formData.append('response_format', 'json');
    const options: RequestOptions = {};
    if (inputArguments.signal) {
        options.signal = inputArguments.signal;
    }
    const response = await requireWebuiTranscriptionsApi(inputArguments.apiClient, inputArguments.context).create(formData, options);
    return response.text;
};

export { requireWebuiSpeechApi, resolveSupportedRecordingMimeType, transcribeAudioBlob };
export type { WebuiMediaApiClient };
