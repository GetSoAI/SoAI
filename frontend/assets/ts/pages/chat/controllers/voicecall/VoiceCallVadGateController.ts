/* SoAI - Voice call VAD gate state machine [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallVadGateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AUDIO_VOICE_ACTIVITY_CONFIDENCE_THRESHOLD, type AudioSpeechScore } from '@core/media/audioSpeechScoring.ts';
import { VoiceCallVadEvidenceWindowController, type VoiceCallVadEvidenceDigest } from '@pages/chat/controllers/voicecall/VoiceCallVadEvidenceWindowController.ts';
import { VOICE_CALL_VAD_ASSISTANT_BARGE_IN_PEAK_RMS, VOICE_CALL_VAD_ASSISTANT_BASELINE_MULTIPLIER, VOICE_CALL_VAD_ASSISTANT_CONFIRM_CONFIDENCE, VOICE_CALL_VAD_ASSISTANT_CONFIRM_HOLD_MS, VOICE_CALL_VAD_ASSISTANT_COOLDOWN_MS, VOICE_CALL_VAD_ASSISTANT_NOISE_REJECT_CONFIDENCE, VOICE_CALL_VAD_ASSISTANT_PRE_ROLL_FRAME_LIMIT, VOICE_CALL_VAD_IMPULSE_REJECT_CONFIDENCE, VOICE_CALL_VAD_MAX_UTTERANCE_MS, VOICE_CALL_VAD_MIN_UTTERANCE_MS, VOICE_CALL_VAD_NOISE_REJECT_CONFIDENCE, VOICE_CALL_VAD_NORMAL_CANDIDATE_CONFIDENCE, VOICE_CALL_VAD_NORMAL_CANDIDATE_HOLD_MS, VOICE_CALL_VAD_NORMAL_CONFIRM_CONFIDENCE, VOICE_CALL_VAD_NORMAL_CONFIRM_HOLD_MS, VOICE_CALL_VAD_NORMAL_PRE_ROLL_FRAME_LIMIT, VOICE_CALL_VAD_PENDING_ABANDON_SILENCE_MS, VOICE_CALL_VAD_SPEECH_STOP_SILENCE_MS, VOICE_CALL_VAD_TONAL_REJECT_CONFIDENCE, VOICE_CALL_VAD_VOICED_CONTINUITY_FLOOR, VOICE_CALL_VAD_WEAK_CONTINUITY_CONFIRM_HOLD_EXTRA_MS } from '@pages/chat/controllers/voicecall/constants.ts';

type VoiceCallVadDecision = { type: 'none' } | { type: 'captureStart'; preRollFrameLimit: number } | { type: 'speechConfirmed' } | { type: 'captureStop'; discard: boolean };

interface VoiceCallVadInput {
    score: AudioSpeechScore;
    nowMs: number;
    assistantAudioActive: boolean;
}

type VoiceCallVadState = 'idle' | 'pending' | 'confirmed';

class VoiceCallVadGateController {
    readonly #evidenceWindow = new VoiceCallVadEvidenceWindowController();
    #state: VoiceCallVadState = 'idle';
    #utteranceStartMs: number | null = null;
    #assistantCooldownUntilMs = 0;
    #overlappedAssistant = false;
    #confirmedCallbackSent = false;

    isUserSpeechConfirmed(): boolean {
        return this.#state === 'confirmed';
    }

    baselineRms(): number {
        return this.#evidenceWindow.baselineRms();
    }

    reset(): void {
        this.#evidenceWindow.reset();
        this.#state = 'idle';
        this.#utteranceStartMs = null;
        this.#assistantCooldownUntilMs = 0;
        this.#overlappedAssistant = false;
        this.#confirmedCallbackSent = false;
    }

    evaluate(input: VoiceCallVadInput): VoiceCallVadDecision {
        const assistantGateActive = this.#resolveAssistantGateActive(input);
        if (this.#state === 'idle') {
            return this.#evaluateIdle(input, assistantGateActive);
        }
        return this.#evaluateCapture(input, assistantGateActive);
    }

    observeIdleFrame(input: VoiceCallVadInput): VoiceCallVadDecision {
        const assistantGateActive = this.#resolveAssistantGateActive(input);
        this.#state = 'idle';
        this.#utteranceStartMs = null;
        this.#overlappedAssistant = false;
        this.#confirmedCallbackSent = false;
        this.#evidenceWindow.observeIdleFrame(input.score, assistantGateActive);
        return { type: 'none' };
    }

    #resolveAssistantGateActive(input: VoiceCallVadInput): boolean {
        if (input.assistantAudioActive) {
            this.#assistantCooldownUntilMs = input.nowMs + VOICE_CALL_VAD_ASSISTANT_COOLDOWN_MS;
            return true;
        }
        return input.nowMs < this.#assistantCooldownUntilMs;
    }

    #evaluateIdle(input: VoiceCallVadInput, assistantGateActive: boolean): VoiceCallVadDecision {
        const potentialSpeech = this.#isPotentialSpeech(input.score, assistantGateActive);
        if (!potentialSpeech) {
            this.#evidenceWindow.observeIdleFrame(input.score, assistantGateActive);
            return { type: 'none' };
        }
        const digest = this.#evidenceWindow.observeEvidence(input.score, input.nowMs, true, false);
        if (digest.positiveEvidenceMs < VOICE_CALL_VAD_NORMAL_CANDIDATE_HOLD_MS) {
            return { type: 'none' };
        }
        this.#state = 'pending';
        this.#utteranceStartMs = input.nowMs;
        this.#overlappedAssistant = assistantGateActive;
        this.#confirmedCallbackSent = false;
        this.#evidenceWindow.resetCaptureEvidence();
        return { type: 'captureStart', preRollFrameLimit: assistantGateActive ? VOICE_CALL_VAD_ASSISTANT_PRE_ROLL_FRAME_LIMIT : VOICE_CALL_VAD_NORMAL_PRE_ROLL_FRAME_LIMIT };
    }

    #evaluateCapture(input: VoiceCallVadInput, assistantGateActive: boolean): VoiceCallVadDecision {
        if (assistantGateActive) {
            this.#overlappedAssistant = true;
        }
        const strictAssistantGateActive = assistantGateActive || this.#overlappedAssistant;
        const potentialSpeech = this.#isPotentialSpeech(input.score, strictAssistantGateActive);
        const cleanSpeech = this.#isCleanSpeech(input.score, strictAssistantGateActive);
        const silentForCapture = this.#state === 'pending' ? !cleanSpeech : !potentialSpeech;
        const digest = this.#evidenceWindow.observeEvidence(input.score, input.nowMs, cleanSpeech, silentForCapture);
        if (this.#state === 'pending' && this.#hasConfirmationReject(digest, strictAssistantGateActive)) {
            return this.#finishCapture(true);
        }
        const confirmation = this.#tryConfirmSpeech(input, strictAssistantGateActive, digest);
        if (confirmation !== null) {
            return confirmation;
        }
        const stopDecision = this.#tryStopCapture(input.nowMs, digest);
        if (stopDecision !== null) {
            return stopDecision;
        }
        return { type: 'none' };
    }

    #isPotentialSpeech(score: AudioSpeechScore, assistantGateActive: boolean): boolean {
        if (this.#hasStartReject(score)) {
            return false;
        }
        const minimumConfidence = assistantGateActive ? VOICE_CALL_VAD_ASSISTANT_CONFIRM_CONFIDENCE : VOICE_CALL_VAD_NORMAL_CANDIDATE_CONFIDENCE;
        const minimumLevel = this.#resolveMinimumLevel(assistantGateActive);
        if (score.confidence >= minimumConfidence && score.level >= minimumLevel) {
            return true;
        }
        return !assistantGateActive && score.voiceActive && score.voiceActivityConfidence >= AUDIO_VOICE_ACTIVITY_CONFIDENCE_THRESHOLD && score.level >= minimumLevel;
    }

    #isCleanSpeech(score: AudioSpeechScore, assistantGateActive: boolean): boolean {
        const noiseRejectConfidence = assistantGateActive ? VOICE_CALL_VAD_ASSISTANT_NOISE_REJECT_CONFIDENCE : VOICE_CALL_VAD_NOISE_REJECT_CONFIDENCE;
        if (!this.#isPotentialSpeech(score, assistantGateActive) || score.noiseConfidence >= noiseRejectConfidence) {
            return false;
        }
        const confidence = assistantGateActive ? VOICE_CALL_VAD_ASSISTANT_CONFIRM_CONFIDENCE : VOICE_CALL_VAD_NORMAL_CONFIRM_CONFIDENCE;
        const adjustedConfidence = score.voicedContinuityConfidence < VOICE_CALL_VAD_VOICED_CONTINUITY_FLOOR ? confidence + 0.08 : confidence;
        return score.confidence >= adjustedConfidence || (!assistantGateActive && score.voiceActive && score.voiceActivityConfidence >= AUDIO_VOICE_ACTIVITY_CONFIDENCE_THRESHOLD);
    }

    #tryConfirmSpeech(input: VoiceCallVadInput, assistantGateActive: boolean, digest: VoiceCallVadEvidenceDigest): VoiceCallVadDecision | null {
        if (this.#state !== 'pending' || this.#confirmedCallbackSent) {
            return null;
        }
        const baseHoldMs = assistantGateActive ? VOICE_CALL_VAD_ASSISTANT_CONFIRM_HOLD_MS : VOICE_CALL_VAD_NORMAL_CONFIRM_HOLD_MS;
        const holdMs = input.score.voicedContinuityConfidence < VOICE_CALL_VAD_VOICED_CONTINUITY_FLOOR ? baseHoldMs + VOICE_CALL_VAD_WEAK_CONTINUITY_CONFIRM_HOLD_EXTRA_MS : baseHoldMs;
        if (!this.#isCleanSpeech(input.score, assistantGateActive) || digest.positiveEvidenceMs < holdMs) {
            return null;
        }
        this.#state = 'confirmed';
        this.#confirmedCallbackSent = true;
        return { type: 'speechConfirmed' };
    }

    #tryStopCapture(nowMs: number, digest: VoiceCallVadEvidenceDigest): VoiceCallVadDecision | null {
        const utteranceStartMs = this.#utteranceStartMs;
        if (utteranceStartMs === null) {
            return this.#finishCapture(true);
        }
        if (nowMs - utteranceStartMs >= VOICE_CALL_VAD_MAX_UTTERANCE_MS) {
            return this.#finishCapture(this.#shouldDiscardFinishedCapture(nowMs, digest));
        }
        if (digest.silenceMs <= 0) {
            return null;
        }
        if (this.#state === 'pending' && digest.silenceMs >= VOICE_CALL_VAD_PENDING_ABANDON_SILENCE_MS) {
            return this.#finishCapture(true);
        }
        const utteranceMs = nowMs - utteranceStartMs;
        if (this.#state === 'confirmed' && digest.silenceMs >= VOICE_CALL_VAD_SPEECH_STOP_SILENCE_MS && utteranceMs >= VOICE_CALL_VAD_MIN_UTTERANCE_MS) {
            return this.#finishCapture(this.#shouldDiscardFinishedCapture(nowMs, digest));
        }
        return null;
    }

    #shouldDiscardFinishedCapture(nowMs: number, digest: VoiceCallVadEvidenceDigest): boolean {
        const utteranceStartMs = this.#utteranceStartMs;
        const utteranceMs = utteranceStartMs === null ? 0 : nowMs - utteranceStartMs;
        return this.#state !== 'confirmed' || utteranceMs < VOICE_CALL_VAD_MIN_UTTERANCE_MS || (this.#overlappedAssistant && digest.peakRms < VOICE_CALL_VAD_ASSISTANT_BARGE_IN_PEAK_RMS);
    }

    #finishCapture(discard: boolean): VoiceCallVadDecision {
        this.#state = 'idle';
        this.#utteranceStartMs = null;
        this.#overlappedAssistant = false;
        this.#confirmedCallbackSent = false;
        this.#evidenceWindow.resetCaptureEvidence();
        return { type: 'captureStop', discard };
    }

    #resolveMinimumLevel(assistantGateActive: boolean): number {
        if (assistantGateActive) {
            return Math.max(VOICE_CALL_VAD_ASSISTANT_BARGE_IN_PEAK_RMS * 0.72, this.#evidenceWindow.baselineRms() * VOICE_CALL_VAD_ASSISTANT_BASELINE_MULTIPLIER);
        }
        return Math.max(0.014, this.#evidenceWindow.baselineRms() * 1.8);
    }

    #hasStartReject(score: AudioSpeechScore): boolean {
        if (score.tonalConfidence >= VOICE_CALL_VAD_TONAL_REJECT_CONFIDENCE) {
            return true;
        }
        return score.impulseConfidence >= VOICE_CALL_VAD_IMPULSE_REJECT_CONFIDENCE && score.voicedContinuityConfidence < VOICE_CALL_VAD_VOICED_CONTINUITY_FLOOR;
    }

    #hasConfirmationReject(digest: VoiceCallVadEvidenceDigest, assistantGateActive: boolean): boolean {
        return (!assistantGateActive && digest.noiseRejectCount >= 2) || digest.tonalRejectCount >= 2 || digest.impulseRejectCount >= 2;
    }
}

export { VoiceCallVadGateController };
export type { VoiceCallVadDecision, VoiceCallVadInput };
