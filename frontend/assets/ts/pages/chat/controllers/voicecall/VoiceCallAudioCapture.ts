/* SoAI - Voice call audio capture orchestration [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallAudioCapture.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import type { CapturedAudioUtterance } from '@core/media/audioCaptureSupport.ts';
import type { VoiceCallRuntimeAssets } from '@core/media/voiceCallRuntimeAssets.ts';
import { extractAudioSpeechFeatures } from '@core/media/audioSpeechFeatures.ts';
import { scoreAudioSpeechFrame } from '@core/media/audioSpeechScoring.ts';
import { VoiceCallAudioGraphController } from '@pages/chat/controllers/voicecall/VoiceCallAudioGraphController.ts';
import { VoiceCallUtteranceBufferController } from '@pages/chat/controllers/voicecall/VoiceCallUtteranceBufferController.ts';
import { VoiceCallVadGateController, type VoiceCallVadDecision } from '@pages/chat/controllers/voicecall/VoiceCallVadGateController.ts';
import { VoiceCallWavEncoderController } from '@pages/chat/controllers/voicecall/VoiceCallWavEncoderController.ts';
import type { VoiceCallAudioFrame } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

interface VoiceCallAudioCaptureHost {
    getAssistantAudioActive(): boolean;
    isRuntimeReady(): boolean;
    onUserSpeechStart(): void;
    onUtterance(utterance: CapturedAudioUtterance): void;
    onError(error: Error): void;
    onLevelChange?(level: number): void;
}

class VoiceCallAudioCapture {
    readonly #host: VoiceCallAudioCaptureHost;
    readonly #runtimeAssets: VoiceCallRuntimeAssets;
    readonly #vadGate = new VoiceCallVadGateController();
    readonly #utteranceBuffer = new VoiceCallUtteranceBufferController();
    readonly #finalizeToken = new SequenceToken();
    #active = false;
    #token = 0;
    #audioGraph: VoiceCallAudioGraphController | null = null;
    #wavEncoder: VoiceCallWavEncoderController | null = null;
    #speechStartNotified = false;

    constructor(host: VoiceCallAudioCaptureHost, runtimeAssets: VoiceCallRuntimeAssets) {
        this.#host = host;
        this.#runtimeAssets = runtimeAssets;
    }

    isActive(): boolean {
        return this.#active;
    }

    isUserSpeechConfirmed(): boolean {
        return this.#vadGate.isUserSpeechConfirmed();
    }

    async start(): Promise<void> {
        if (this.#active) {
            return;
        }
        this.#active = true;
        this.#token += 1;
        const token = this.#token;
        this.#vadGate.reset();
        this.#utteranceBuffer.reset();
        this.#speechStartNotified = false;
        const audioGraph = new VoiceCallAudioGraphController(this.#runtimeAssets.captureWorkletUrl);
        this.#audioGraph = audioGraph;
        try {
            await audioGraph.start(
                (frame) => this.#handleFrame(token, frame),
                (error) => this.#handleGraphError(token, error)
            );
            if (!this.#isCurrentToken(token)) {
                await audioGraph.stop();
            }
        } catch (error) {
            if (this.#isCurrentToken(token)) {
                this.#active = false;
                this.#token += 1;
                this.#audioGraph = null;
                this.#vadGate.reset();
                this.#utteranceBuffer.reset();
            }
            throw error;
        }
    }

    async stop(): Promise<void> {
        if (!this.#active && this.#audioGraph === null) {
            return;
        }
        this.#active = false;
        this.#token += 1;
        this.#finalizeToken.invalidate();
        this.#vadGate.reset();
        this.#utteranceBuffer.discardCapture();
        this.#speechStartNotified = false;
        this.#disposeWavEncoder();
        const audioGraph = this.#audioGraph;
        this.#audioGraph = null;
        if (audioGraph) {
            await audioGraph.stop();
        }
        this.#utteranceBuffer.reset();
    }

    async pause(): Promise<void> {
        await this.stop();
    }

    async resume(): Promise<void> {
        await this.start();
    }

    #isCurrentToken(token: number): boolean {
        return this.#active && token === this.#token;
    }

    #isCurrentFinalizeToken(captureToken: number, finalizeToken: number): boolean {
        return this.#isCurrentToken(captureToken) && this.#finalizeToken.isActive(finalizeToken);
    }

    #handleFrame(token: number, frame: VoiceCallAudioFrame): void {
        if (!this.#isCurrentToken(token)) {
            return;
        }
        const features = extractAudioSpeechFeatures({
            samples: frame.samples,
            frequencyData: frame.frequencyData,
            sampleRate: frame.sampleRate
        });
        const score = scoreAudioSpeechFrame(features, this.#vadGate.baselineRms());
        this.#host.onLevelChange?.(score.level);
        if (!this.#host.isRuntimeReady()) {
            this.#vadGate.observeIdleFrame({
                score,
                nowMs: frame.nowMs,
                assistantAudioActive: this.#host.getAssistantAudioActive()
            });
            this.#utteranceBuffer.discardCapture();
            this.#utteranceBuffer.reset();
            this.#speechStartNotified = false;
            return;
        }
        this.#utteranceBuffer.pushPreRollFrame(frame.samples);
        const wasCapturing = this.#utteranceBuffer.isCapturing();
        const decision = this.#vadGate.evaluate({
            score,
            nowMs: frame.nowMs,
            assistantAudioActive: this.#host.getAssistantAudioActive()
        });
        this.#applyDecision(token, frame, decision, wasCapturing);
    }

    #applyDecision(token: number, frame: VoiceCallAudioFrame, decision: VoiceCallVadDecision, wasCapturing: boolean): void {
        if (decision.type === 'captureStart') {
            this.#utteranceBuffer.beginCapture(decision.preRollFrameLimit);
            return;
        }
        if (wasCapturing && decision.type !== 'captureStop') {
            this.#utteranceBuffer.appendCaptureFrame(frame.samples);
        }
        if (decision.type === 'speechConfirmed') {
            this.#notifyUserSpeechStart();
            return;
        }
        if (decision.type === 'captureStop') {
            void this.#finishUtterance(token, frame.sampleRate, decision.discard).catch((error) => {
                this.#handleFinalizeError(token, error);
            });
        }
    }

    async #finishUtterance(token: number, sampleRate: number, discard: boolean): Promise<void> {
        const frames = this.#utteranceBuffer.finishCapture();
        this.#speechStartNotified = false;
        if (discard || frames.length === 0) {
            return;
        }
        const finalizeToken = this.#finalizeToken.next();
        if (!this.#isCurrentFinalizeToken(token, finalizeToken)) {
            return;
        }
        const blob = await this.#requireWavEncoder().encode(frames, sampleRate);
        if (!this.#isCurrentFinalizeToken(token, finalizeToken) || blob.size < 1) {
            return;
        }
        const utterance: CapturedAudioUtterance = { blob, mimeType: 'audio/wav' };
        this.#host.onUtterance(utterance);
    }

    #notifyUserSpeechStart(): void {
        if (this.#speechStartNotified) {
            return;
        }
        this.#speechStartNotified = true;
        this.#finalizeToken.invalidate();
        this.#wavEncoder?.cancel();
        this.#host.onUserSpeechStart();
    }

    #requireWavEncoder(): VoiceCallWavEncoderController {
        if (!this.#wavEncoder) {
            this.#wavEncoder = new VoiceCallWavEncoderController(this.#runtimeAssets.wavEncoderWorkerUrl);
        }
        return this.#wavEncoder;
    }

    #disposeWavEncoder(): void {
        const wavEncoder = this.#wavEncoder;
        this.#wavEncoder = null;
        wavEncoder?.dispose();
    }

    #handleGraphError(token: number, error: Error): void {
        if (!this.#isCurrentToken(token)) {
            return;
        }
        void this.#stopAfterGraphError(token, error).catch((stopError) => {
            errorHandler.warn('VoiceCallAudioCapture', 'Failed to stop after voice call audio graph error', ensureError(stopError));
        });
    }

    async #stopAfterGraphError(token: number, error: Error): Promise<void> {
        if (!this.#isCurrentToken(token)) {
            return;
        }
        errorHandler.warn('VoiceCallAudioCapture', 'Voice call audio graph failed', ensureError(error));
        try {
            this.#host.onError(error);
        } finally {
            await this.stop();
        }
    }

    #handleFinalizeError(token: number, error: Error): void {
        if (!this.#isCurrentToken(token)) {
            return;
        }
        errorHandler.warn('VoiceCallAudioCapture', 'Failed to finalize utterance recording', ensureError(error));
        this.#host.onError(new Error(i18n.t('chat.audio.recordingFailed')));
    }
}

export { VoiceCallAudioCapture };
