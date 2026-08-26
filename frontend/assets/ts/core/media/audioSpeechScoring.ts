/* SoAI - Browser audio speech confidence scoring [frontend/assets/ts/core/media/audioSpeechScoring.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clamp01 } from '@core/media/audioCaptureSupport.ts';
import type { AudioSpeechFeatures } from '@core/media/audioSpeechFeatures.ts';

interface AudioSpeechScore {
    confidence: number;
    speechLike: boolean;
    voiceActivityConfidence: number;
    voiceActive: boolean;
    level: number;
    impulseConfidence: number;
    tonalConfidence: number;
    noiseConfidence: number;
    voicedContinuityConfidence: number;
}

const AUDIO_VOICE_ACTIVITY_CONFIDENCE_THRESHOLD = 0.52;

const scoreRange = (value: number, low: number, high: number): number => {
    if (value <= low) {
        return 0;
    }
    if (value >= high) {
        return 1;
    }
    return (value - low) / (high - low);
};

const scoreCenteredRange = (value: number, low: number, center: number, high: number): number => {
    if (value <= low || value >= high) {
        return 0;
    }
    if (value === center) {
        return 1;
    }
    if (value < center) {
        return (value - low) / (center - low);
    }
    return (high - value) / (high - center);
};

const scoreAudioSpeechFrame = (features: AudioSpeechFeatures, baselineRms: number): AudioSpeechScore => {
    const adaptiveFloor = Math.max(0.012, baselineRms * 2.2);
    const noiseConfidence = Math.max(scoreRange(features.lowBandRatio, 0.42, 0.8), scoreRange(features.highBandRatio, 0.32, 0.68));
    const impulseConfidence = scoreRange(features.crestFactor, 8, 18);
    const tonalConfidence = scoreRange(features.voiceBandPeakRatio, 0.72, 0.92);
    const voicedContinuityConfidence = scoreRange(features.periodicity, 0.12, 0.38);
    if (features.rms < adaptiveFloor || features.peak < 0.018) {
        return {
            confidence: 0,
            speechLike: false,
            voiceActivityConfidence: 0,
            voiceActive: false,
            level: features.rms,
            impulseConfidence,
            tonalConfidence,
            noiseConfidence,
            voicedContinuityConfidence
        };
    }
    const energyScore = scoreRange(features.rms, adaptiveFloor, Math.max(0.08, baselineRms * 6));
    const voiceBandScore = scoreRange(features.voiceBandRatio, 0.45, 0.78);
    const coverageScore = scoreRange(features.voiceBandCoverage, 0.24, 0.72);
    const centroidScore = scoreCenteredRange(features.spectralCentroidHz, 180, 1_350, 4_500);
    const zeroCrossingScore = scoreCenteredRange(features.zeroCrossingRate, 0.012, 0.08, 0.26);
    const voiceActivityConfidence = clamp01(energyScore * 0.34 + voiceBandScore * 0.24 + coverageScore * 0.16 + centroidScore * 0.12 + zeroCrossingScore * 0.08 + voicedContinuityConfidence * 0.06 - noiseConfidence * 0.36 - impulseConfidence * 0.28 - tonalConfidence * 0.2);
    const confidence = clamp01(energyScore * 0.2 + voiceBandScore * 0.24 + coverageScore * 0.18 + voicedContinuityConfidence * 0.18 + centroidScore * 0.12 + zeroCrossingScore * 0.08 - noiseConfidence * 0.35 - impulseConfidence * 0.3 - tonalConfidence * 0.24);
    return {
        confidence,
        speechLike: confidence >= 0.55,
        voiceActivityConfidence,
        voiceActive: voiceActivityConfidence >= AUDIO_VOICE_ACTIVITY_CONFIDENCE_THRESHOLD,
        level: features.rms,
        impulseConfidence,
        tonalConfidence,
        noiseConfidence,
        voicedContinuityConfidence
    };
};

export { AUDIO_VOICE_ACTIVITY_CONFIDENCE_THRESHOLD, scoreAudioSpeechFrame };
export type { AudioSpeechScore };
