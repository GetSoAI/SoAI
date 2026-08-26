/* SoAI - Chat feature TTS OpenAI audio [frontend/assets/ts/features/chat/tts/chatTtsOpenAiAudio.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { requireWebuiSpeechApi, type WebuiMediaApiClient } from '@features/chat/api/webuiMediaAudio.ts';

type TtsResponseFormat = 'wav';

interface OpenAiSpeechPayload {
    model: string;
    input: string;
    voice?: string;
    responseFormat: TtsResponseFormat;
    speed: number;
}

const serializeOpenAiSpeechPayload = (payload: OpenAiSpeechPayload): JsonObject => ({
    model: payload.model,
    input: payload.input,
    ...(payload.voice === undefined ? {} : { voice: payload.voice }),
    'response_format': payload.responseFormat,
    speed: payload.speed
});

const MAX_ERROR_BODY_PREVIEW_BYTES = 16_384;

const isRiffWavPayload = (buffer: ArrayBuffer): boolean => {
    if (buffer.byteLength < 12) {
        return false;
    }
    const bytes = new Uint8Array(buffer);
    const riff = bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46;
    const wave = bytes[8] === 0x57 && bytes[9] === 0x41 && bytes[10] === 0x56 && bytes[11] === 0x45;
    return riff && wave;
};

const readUtf8Preview = (buffer: ArrayBuffer): string => {
    const slice = buffer.byteLength > MAX_ERROR_BODY_PREVIEW_BYTES ? buffer.slice(0, MAX_ERROR_BODY_PREVIEW_BYTES) : buffer;
    try {
        return new TextDecoder('utf-8', { fatal: false }).decode(slice).trim();
    } catch (_error) {
        errorHandler.debug('ChatTtsManager', 'Failed decoding error body preview', ensureError(_error));
        return '';
    }
};

const fetchOpenAiAudioUrl = async (apiClient: WebuiMediaApiClient | null, payload: OpenAiSpeechPayload, signal: AbortSignal): Promise<string> => {
    const responseValue = await requireWebuiSpeechApi(apiClient, 'ChatTtsManager').create(serializeOpenAiSpeechPayload(payload), { signal });
    if (!(responseValue instanceof Response)) {
        throw new Error('ChatTtsManager expected Response from webui.media.audio.speech.create()');
    }
    const contentType = responseValue.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
        const raw = await responseValue.arrayBuffer();
        const preview = readUtf8Preview(raw);
        const hint = preview ? ` (body preview: ${preview.slice(0, 256)})` : '';
        throw new Error(`Text-to-speech response was not a binary audio payload${hint}`);
    }
    const raw = await responseValue.arrayBuffer();
    if (raw.byteLength < 1) {
        throw new Error('ChatTtsManager received empty audio payload');
    }
    if (payload.responseFormat === 'wav' && !isRiffWavPayload(raw)) {
        const preview = readUtf8Preview(raw);
        const hint = preview ? ` (body preview: ${preview.slice(0, 256)})` : '';
        throw new Error(`Text-to-speech response was not a valid WAV payload${hint}`);
    }
    const mimeType = payload.responseFormat === 'wav' ? 'audio/wav' : '';
    const blob = new Blob([raw], { type: mimeType });
    return URL.createObjectURL(blob);
};

export { fetchOpenAiAudioUrl };
export type { OpenAiSpeechPayload, TtsResponseFormat };
