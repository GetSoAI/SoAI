/* SoAI - Voice call WAV worker protocol [frontend/assets/ts/core/media/voiceCallWavWorkerProtocol.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface VoiceCallWavEncodeRequest {
    type: 'encode';
    requestId: number;
    frames: Float32Array[];
    sampleRate: number;
}

type VoiceCallWavEncodeResponse = { type: 'encoded'; requestId: number; blob: Blob } | { type: 'error'; requestId: number; message: string };

interface VoiceCallWavEncodeCandidate {
    type?: string | undefined;
    requestId?: number | undefined;
    frames?: Float32Array[] | undefined;
    sampleRate?: number | undefined;
}

interface VoiceCallWavResponseCandidate {
    type?: string | undefined;
    requestId?: number | undefined;
    blob?: Blob | undefined;
    message?: string | undefined;
}

type VoiceCallWavProtocolCandidate = VoiceCallWavEncodeCandidate | VoiceCallWavResponseCandidate | JsonValue | null | undefined;

const isFloat32ArrayList = (value: readonly Float32Array[] | null | undefined): value is Float32Array[] => {
    if (!Array.isArray(value)) {
        return false;
    }
    return value.every((entry) => entry instanceof Float32Array);
};

const isVoiceCallWavEncodeRequest = (value: VoiceCallWavProtocolCandidate): value is VoiceCallWavEncodeRequest => {
    if (!isObject(value)) {
        return false;
    }
    const candidate: VoiceCallWavEncodeCandidate = value;
    return candidate.type === 'encode' && isNumber(candidate.requestId) && Number.isInteger(candidate.requestId) && isFloat32ArrayList(candidate.frames) && isNumber(candidate.sampleRate);
};

const isVoiceCallWavEncodeResponse = (value: VoiceCallWavProtocolCandidate): value is VoiceCallWavEncodeResponse => {
    if (!isObject(value)) {
        return false;
    }
    const candidate: VoiceCallWavResponseCandidate = value;
    if (candidate.type === 'encoded') {
        return isNumber(candidate.requestId) && candidate.blob instanceof Blob;
    }
    return candidate.type === 'error' && isNumber(candidate.requestId) && isString(candidate.message);
};

export { isVoiceCallWavEncodeRequest, isVoiceCallWavEncodeResponse };
export type { VoiceCallWavEncodeRequest, VoiceCallWavEncodeResponse };
