/* SoAI - Voice call microphone audio graph [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallAudioGraphController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveAudioContextConstructor } from '@core/media/audioCaptureSupport.ts';
import { AudioCaptureFailure, toAudioCaptureFailure } from '@core/media/mediaCaptureErrors.ts';
import { closeAudioContextSafe, stopMediaStreamTracks } from '@core/media/mediaCleanup.ts';
import { isFunction } from '@core/typeGuards.ts';
import { VoiceCallCaptureWorkletController } from '@pages/chat/controllers/voicecall/VoiceCallCaptureWorkletController.ts';
import type { VoiceCallAudioFrame } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

const ANALYSER_FFT_SIZE = 2_048;

class VoiceCallAudioGraphController {
    readonly #workletUrl: string;
    #stream: MediaStream | null = null;
    #audioContext: AudioContext | null = null;
    #source: MediaStreamAudioSourceNode | null = null;
    #analyser: AnalyserNode | null = null;
    #bridge: VoiceCallCaptureWorkletController | null = null;
    #stopped = true;

    constructor(workletUrl: string) {
        this.#workletUrl = workletUrl;
    }

    async start(onFrame: (frame: VoiceCallAudioFrame) => void, onError: (error: Error) => void): Promise<void> {
        this.#stopped = false;
        if (!isFunction(navigator?.mediaDevices?.getUserMedia)) {
            throw new AudioCaptureFailure('capture_unsupported');
        }
        const AudioContextConstructor = this.#resolveAudioContextConstructor();
        let stream: MediaStream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
        } catch (error) {
            throw toAudioCaptureFailure(ensureError(error));
        }
        this.#stream = stream;
        if (this.#stopped) {
            await this.stop();
            return;
        }
        try {
            let audioContext: AudioContext;
            try {
                audioContext = new AudioContextConstructor();
                this.#audioContext = audioContext;
                if (audioContext.state === 'suspended') await audioContext.resume();
            } catch (error) {
                throw new AudioCaptureFailure('audio_context_unavailable', ensureError(error));
            }
            if (this.#stopped) {
                await this.stop();
                return;
            }
            await this.#connect(stream, audioContext, onFrame, onError);
        } catch (error) {
            const failure = toAudioCaptureFailure(ensureError(error));
            await this.#stopAfterStartFailure();
            throw failure;
        }
    }

    async stop(): Promise<void> {
        this.#stopped = true;
        const bridge = this.#bridge;
        this.#bridge = null;
        if (bridge) {
            bridge.stop();
        }
        const analyser = this.#analyser;
        this.#analyser = null;
        if (analyser) {
            this.#disconnectNode(analyser, 'analyser');
        }
        const source = this.#source;
        this.#source = null;
        if (source) {
            this.#disconnectNode(source, 'source');
        }
        const stream = this.#stream;
        this.#stream = null;
        stopMediaStreamTracks(stream);
        const audioContext = this.#audioContext;
        this.#audioContext = null;
        await closeAudioContextSafe(audioContext, 'voice call graph stop');
    }

    #resolveAudioContextConstructor(): typeof AudioContext {
        try {
            return resolveAudioContextConstructor();
        } catch (error) {
            throw new AudioCaptureFailure('audio_context_unavailable', ensureError(error));
        }
    }

    async #stopAfterStartFailure(): Promise<void> {
        try {
            await this.stop();
        } catch (cleanupError) {
            errorHandler.warn('VoiceCallAudioGraphController', 'Voice call audio graph cleanup after start failure failed', ensureError(cleanupError));
        }
    }

    async #connect(stream: MediaStream, audioContext: AudioContext, onFrame: (frame: VoiceCallAudioFrame) => void, onError: (error: Error) => void): Promise<void> {
        const source = audioContext.createMediaStreamSource(stream);
        this.#source = source;
        const analyser = audioContext.createAnalyser();
        this.#analyser = analyser;
        analyser.fftSize = ANALYSER_FFT_SIZE;
        analyser.smoothingTimeConstant = 0;
        const frequencyData = new Uint8Array(analyser.frequencyBinCount);
        const bridge = await VoiceCallCaptureWorkletController.create({
            audioContext,
            analyser,
            frequencyData,
            workletUrl: this.#workletUrl,
            onFrame,
            onError
        });
        if (this.#stopped) {
            bridge.stop();
            return;
        }
        this.#bridge = bridge;
        source.connect(analyser);
        bridge.connect(source);
    }

    #disconnectNode(node: AudioNode, label: string): void {
        try {
            node.disconnect();
        } catch (error) {
            errorHandler.warn('VoiceCallAudioGraphController', `Failed to disconnect ${label}`, ensureError(error));
        }
    }
}

export { VoiceCallAudioGraphController };
