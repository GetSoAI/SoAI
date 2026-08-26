/* SoAI - Voice call WAV encoder worker entrypoint [frontend/assets/ts/app/entrypoints/voicecall/voiceCallWavEncoderWorker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { encodeWavPcm16Mono } from '@core/media/wavPcm16MonoEncoding.ts';
import { isVoiceCallWavEncodeRequest, type VoiceCallWavEncodeRequest, type VoiceCallWavEncodeResponse } from '@core/media/voiceCallWavWorkerProtocol.ts';

const post = (message: VoiceCallWavEncodeResponse): void => {
    globalThis.postMessage(message);
};

globalThis.onmessage = (event: MessageEvent<VoiceCallWavEncodeRequest | null>): void => {
    const candidate = event.data;
    if (!isVoiceCallWavEncodeRequest(candidate)) {
        post({ type: 'error', requestId: 0, message: 'Voice call WAV worker received an invalid request' });
        return;
    }
    try {
        const blob = encodeWavPcm16Mono(candidate.frames, candidate.sampleRate);
        post({ type: 'encoded', requestId: candidate.requestId, blob });
    } catch (error) {
        post({ type: 'error', requestId: candidate.requestId, message: ensureError(error).message || 'Voice call WAV encoding failed' });
    }
};
