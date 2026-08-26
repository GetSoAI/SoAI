/* SoAI - Voice call VAD rolling evidence window [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallVadEvidenceWindowController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clamp01 } from '@core/media/audioCaptureSupport.ts';
import type { AudioSpeechScore } from '@core/media/audioSpeechScoring.ts';
import { VOICE_CALL_VAD_IMPULSE_REJECT_CONFIDENCE, VOICE_CALL_VAD_NOISE_REJECT_CONFIDENCE, VOICE_CALL_VAD_TONAL_REJECT_CONFIDENCE } from '@pages/chat/controllers/voicecall/constants.ts';

interface VoiceCallVadEvidenceDigest {
    positiveEvidenceMs: number;
    silenceMs: number;
    impulseRejectCount: number;
    noiseRejectCount: number;
    tonalRejectCount: number;
    peakRms: number;
}

class VoiceCallVadEvidenceWindowController {
    #baselineRms = 0.01;
    #lastFrameMs: number | null = null;
    #positiveEvidenceMs = 0;
    #silenceMs = 0;
    #impulseRejectCount = 0;
    #noiseRejectCount = 0;
    #tonalRejectCount = 0;
    #peakRms = 0;

    baselineRms(): number {
        return this.#baselineRms;
    }

    reset(): void {
        this.#baselineRms = 0.01;
        this.resetCaptureEvidence();
    }

    resetCaptureEvidence(): void {
        this.#lastFrameMs = null;
        this.#positiveEvidenceMs = 0;
        this.#silenceMs = 0;
        this.#impulseRejectCount = 0;
        this.#noiseRejectCount = 0;
        this.#tonalRejectCount = 0;
        this.#peakRms = 0;
    }

    observeIdleFrame(score: AudioSpeechScore, assistantGateActive: boolean): void {
        this.resetCaptureEvidence();
        this.#updateBaseline(score, assistantGateActive);
    }

    observeEvidence(score: AudioSpeechScore, nowMs: number, positiveEvidence: boolean, cleanSilence: boolean): VoiceCallVadEvidenceDigest {
        const elapsedMs = this.#resolveElapsedMs(nowMs);
        this.#peakRms = Math.max(this.#peakRms, score.level);
        if (positiveEvidence) {
            this.#positiveEvidenceMs += elapsedMs;
            this.#silenceMs = 0;
        } else {
            this.#positiveEvidenceMs = 0;
            if (cleanSilence) {
                this.#silenceMs += elapsedMs;
            } else {
                this.#silenceMs = 0;
            }
        }
        if (score.impulseConfidence >= VOICE_CALL_VAD_IMPULSE_REJECT_CONFIDENCE) {
            this.#impulseRejectCount += 1;
        }
        if (score.noiseConfidence >= VOICE_CALL_VAD_NOISE_REJECT_CONFIDENCE) {
            this.#noiseRejectCount += 1;
        }
        if (score.tonalConfidence >= VOICE_CALL_VAD_TONAL_REJECT_CONFIDENCE) {
            this.#tonalRejectCount += 1;
        }
        return this.digest();
    }

    digest(): VoiceCallVadEvidenceDigest {
        return {
            positiveEvidenceMs: this.#positiveEvidenceMs,
            silenceMs: this.#silenceMs,
            impulseRejectCount: this.#impulseRejectCount,
            noiseRejectCount: this.#noiseRejectCount,
            tonalRejectCount: this.#tonalRejectCount,
            peakRms: this.#peakRms
        };
    }

    #resolveElapsedMs(nowMs: number): number {
        const lastFrameMs = this.#lastFrameMs;
        this.#lastFrameMs = nowMs;
        if (lastFrameMs === null) {
            return 0;
        }
        return Math.max(0, Math.min(120, nowMs - lastFrameMs));
    }

    #updateBaseline(score: AudioSpeechScore, assistantGateActive: boolean): void {
        if (assistantGateActive || score.speechLike || score.voiceActive || score.level >= 0.04) {
            return;
        }
        const nextBaseline = this.#baselineRms * 0.94 + score.level * 0.06;
        this.#baselineRms = clamp01(Math.max(0.004, Math.min(0.055, nextBaseline)));
    }
}

export { VoiceCallVadEvidenceWindowController };
export type { VoiceCallVadEvidenceDigest };
