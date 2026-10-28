/* SoAI - WebUI media audio helpers for chat features [frontend/assets/ts/features/chat/api/webuiMediaAudio.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpenAiTranscriptionResponse } from '@core/api/contracts/openAiResponseContracts.ts';
import { TRANSCRIPTION_CANCELLATION_UNCONFIRMED_CODE, TRANSCRIPTION_DEADLINE_EXCEEDED_CODE, type TranscriptionRequestOptions } from '@core/api/endpoints/openaiWsAudioTranscription.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { APIError } from '@core/apiError.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveOperationCauseMessage } from '@core/errors/operationCausePresentation.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

interface WebuiTranscriptionsApi {
    create(payload: FormData, options?: TranscriptionRequestOptions): Promise<OpenAiTranscriptionResponse>;
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
    onDeadlineSettlement?: (() => void) | undefined;
    context: string;
}

const RECORDING_MIME_TYPES: readonly string[] = Object.freeze(['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4', 'audio/wav']);

type WebuiTranscriptionMethod = (payload: FormData, options?: TranscriptionRequestOptions) => Promise<OpenAiTranscriptionResponse>;
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
        create: (payload: FormData, options?: TranscriptionRequestOptions): Promise<OpenAiTranscriptionResponse> => create(payload, options)
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
    const options: TranscriptionRequestOptions = { onDeadlineSettlement: inputArguments.onDeadlineSettlement };
    if (inputArguments.signal) {
        options.signal = inputArguments.signal;
    }
    try {
        const response = await requireWebuiTranscriptionsApi(inputArguments.apiClient, inputArguments.context).create(formData, options);
        return response.text;
    } catch (error) {
        if (error instanceof APIError && error.code === 'transcription_model_unavailable') notifyHandledOperationError(error);
        throw error;
    }
};

const resolveTranscriptionFailureText = (error: Error, fallback: string): string => {
    if (!(error instanceof APIError)) return fallback;
    if (error.code === TRANSCRIPTION_DEADLINE_EXCEEDED_CODE) return i18n.t('chat.audio.transcriptionDeadlineExceeded');
    if (error.code !== TRANSCRIPTION_CANCELLATION_UNCONFIRMED_CODE) return resolveOperationCauseMessage(error.code ?? null, error) ?? fallback;
    return error.taskId ? i18n.t('chat.audio.transcriptionCancellationUnconfirmedReference', { reference: error.taskId }) : i18n.t('chat.audio.transcriptionCancellationUnconfirmed');
};

export { requireWebuiSpeechApi, resolveSupportedRecordingMimeType, resolveTranscriptionFailureText, transcribeAudioBlob };
export type { WebuiMediaApiClient };
