/* SoAI - Voice call capture AudioWorklet controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallCaptureWorkletController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { VOICE_CALL_CAPTURE_PROCESSOR_NAME } from '@core/media/voiceCallCaptureWorkletConstants.ts';
import { isVoiceCallCaptureWorkletFrameMessage } from '@core/media/voiceCallCaptureWorkletProtocol.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { VoiceCallAudioFrame } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

interface VoiceCallCaptureWorkletControllerArguments {
    audioContext: AudioContext;
    analyser: AnalyserNode;
    frequencyData: Uint8Array<ArrayBuffer>;
    workletUrl: string;
    onFrame(frame: VoiceCallAudioFrame): void;
    onError(error: Error): void;
}

class VoiceCallCaptureWorkletController {
    readonly #audioContext: AudioContext;
    readonly #analyser: AnalyserNode;
    readonly #frequencyData: Uint8Array<ArrayBuffer>;
    readonly #onFrame: (frame: VoiceCallAudioFrame) => void;
    readonly #onError: (error: Error) => void;
    #node: AudioWorkletNode | null = null;
    #gain: GainNode | null = null;
    #stopped = false;

    private constructor(inputArguments: VoiceCallCaptureWorkletControllerArguments) {
        this.#audioContext = inputArguments.audioContext;
        this.#analyser = inputArguments.analyser;
        this.#frequencyData = inputArguments.frequencyData;
        this.#onFrame = inputArguments.onFrame;
        this.#onError = inputArguments.onError;
    }

    static async create(inputArguments: VoiceCallCaptureWorkletControllerArguments): Promise<VoiceCallCaptureWorkletController> {
        if (!inputArguments.audioContext.audioWorklet || !isFunction(inputArguments.audioContext.audioWorklet.addModule)) {
            throw new Error(i18n.t('chat.voiceCall.recordingUnavailable'));
        }
        await inputArguments.audioContext.audioWorklet.addModule(inputArguments.workletUrl);
        const bridge = new VoiceCallCaptureWorkletController(inputArguments);
        bridge.#initialize();
        return bridge;
    }

    connect(source: MediaStreamAudioSourceNode): void {
        const node = this.#node;
        if (!node) {
            throw new Error(i18n.t('chat.voiceCall.recordingUnavailable'));
        }
        source.connect(node);
    }

    stop(): void {
        this.#stopped = true;
        const node = this.#node;
        this.#node = null;
        if (node) {
            node.port.onmessage = null;
            node.onprocessorerror = null;
            node.port.close();
            this.#disconnectNode(node, 'worklet');
        }
        const gain = this.#gain;
        this.#gain = null;
        if (gain) {
            this.#disconnectNode(gain, 'gain');
        }
    }

    #initialize(): void {
        const node = new AudioWorkletNode(this.#audioContext, VOICE_CALL_CAPTURE_PROCESSOR_NAME, { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] });
        const gain = this.#audioContext.createGain();
        gain.gain.value = 0;
        node.port.onmessage = (event: MessageEvent): void => this.#handleMessage(event.data);
        node.onprocessorerror = (): void => this.#handleProcessorError();
        node.connect(gain);
        gain.connect(this.#audioContext.destination);
        this.#node = node;
        this.#gain = gain;
    }

    #handleMessage(value: JsonValue): void {
        if (this.#stopped) {
            return;
        }
        const message = typeof value === 'object' ? value : null;
        if (!isVoiceCallCaptureWorkletFrameMessage(message)) {
            this.#stopAfterFatalError(new Error(i18n.t('chat.voiceCall.recordingUnavailable')));
            return;
        }
        this.#analyser.getByteFrequencyData(this.#frequencyData);
        this.#onFrame({
            samples: message.samples,
            frequencyData: new Uint8Array(this.#frequencyData),
            sampleRate: this.#audioContext.sampleRate,
            nowMs: performance.now()
        });
    }

    #handleProcessorError(): void {
        if (!this.#stopped) {
            this.#stopAfterFatalError(new Error(i18n.t('chat.voiceCall.recordingUnavailable')));
        }
    }

    #stopAfterFatalError(error: Error): void {
        this.stop();
        this.#onError(error);
    }

    #disconnectNode(node: AudioNode, label: string): void {
        try {
            node.disconnect();
        } catch (error) {
            errorHandler.warn('VoiceCallCaptureWorkletController', `Failed to disconnect ${label}`, ensureError(error));
        }
    }
}

export { VoiceCallCaptureWorkletController };
