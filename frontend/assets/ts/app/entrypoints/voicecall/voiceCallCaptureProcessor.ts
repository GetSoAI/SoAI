/* SoAI - Voice call capture AudioWorklet entrypoint [frontend/assets/ts/app/entrypoints/voicecall/voiceCallCaptureProcessor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { VOICE_CALL_CAPTURE_FRAME_SIZE, VOICE_CALL_CAPTURE_PROCESSOR_NAME } from '@core/media/voiceCallCaptureWorkletConstants.ts';
import type { VoiceCallCaptureWorkletFrameMessage } from '@core/media/voiceCallCaptureWorkletProtocol.ts';

class VoiceCallCaptureProcessor extends AudioWorkletProcessor {
    readonly #buffer = new Float32Array(VOICE_CALL_CAPTURE_FRAME_SIZE);
    #writeOffset = 0;

    process(inputs: Float32Array[][]): boolean {
        const channels = inputs[0];
        const input = channels ? channels[0] : undefined;
        if (!input || input.length < 1) {
            return true;
        }
        let readOffset = 0;
        while (readOffset < input.length) {
            const available = input.length - readOffset;
            const writable = VOICE_CALL_CAPTURE_FRAME_SIZE - this.#writeOffset;
            const count = Math.min(available, writable);
            this.#buffer.set(input.subarray(readOffset, readOffset + count), this.#writeOffset);
            this.#writeOffset += count;
            readOffset += count;
            if (this.#writeOffset === VOICE_CALL_CAPTURE_FRAME_SIZE) {
                const samples = new Float32Array(this.#buffer);
                const message: VoiceCallCaptureWorkletFrameMessage = { type: 'frame', samples };
                this.port.postMessage(message, [samples.buffer]);
                this.#writeOffset = 0;
            }
        }
        return true;
    }
}

registerProcessor(VOICE_CALL_CAPTURE_PROCESSOR_NAME, VoiceCallCaptureProcessor);
