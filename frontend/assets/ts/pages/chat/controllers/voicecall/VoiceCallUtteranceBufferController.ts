/* SoAI - Voice call utterance frame buffering [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallUtteranceBufferController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { VOICE_CALL_VAD_ASSISTANT_PRE_ROLL_FRAME_LIMIT, VOICE_CALL_VAD_NORMAL_PRE_ROLL_FRAME_LIMIT } from '@pages/chat/controllers/voicecall/constants.ts';

const PRE_ROLL_FRAME_CAP = Math.max(VOICE_CALL_VAD_ASSISTANT_PRE_ROLL_FRAME_LIMIT, VOICE_CALL_VAD_NORMAL_PRE_ROLL_FRAME_LIMIT);

class VoiceCallUtteranceBufferController {
    #preRollFrames: Float32Array[] = [];
    #pcmFrames: Float32Array[] = [];
    #capturing = false;

    isCapturing(): boolean {
        return this.#capturing;
    }

    reset(): void {
        this.#preRollFrames = [];
        this.#pcmFrames = [];
        this.#capturing = false;
    }

    pushPreRollFrame(frame: Float32Array): void {
        this.#preRollFrames.push(frame);
        while (this.#preRollFrames.length > PRE_ROLL_FRAME_CAP) {
            this.#preRollFrames.shift();
        }
    }

    beginCapture(preRollFrameLimit: number): void {
        const frames = this.#preRollFrames.slice(-preRollFrameLimit);
        this.#pcmFrames = frames.map((frame) => new Float32Array(frame));
        this.#capturing = true;
    }

    appendCaptureFrame(frame: Float32Array): void {
        if (this.#capturing) {
            this.#pcmFrames.push(new Float32Array(frame));
        }
    }

    finishCapture(): Float32Array[] {
        const frames = this.#pcmFrames;
        this.#pcmFrames = [];
        this.#capturing = false;
        return frames;
    }

    discardCapture(): void {
        this.#pcmFrames = [];
        this.#capturing = false;
    }
}

export { VoiceCallUtteranceBufferController };
