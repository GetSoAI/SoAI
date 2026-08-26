/* SoAI - Voice call capture worklet protocol [frontend/assets/ts/core/media/voiceCallCaptureWorkletProtocol.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject } from '@core/typeGuards.ts';

interface VoiceCallCaptureWorkletFrameMessage {
    type: 'frame';
    samples: Float32Array;
}

const isVoiceCallCaptureWorkletFrameMessage = <T>(value: T): value is T & VoiceCallCaptureWorkletFrameMessage => {
    if (!isObject(value)) {
        return false;
    }
    return 'type' in value && value.type === 'frame' && 'samples' in value && value.samples instanceof Float32Array;
};

export { isVoiceCallCaptureWorkletFrameMessage };
export type { VoiceCallCaptureWorkletFrameMessage };
