/* SoAI - Browser audio speech feature extraction [frontend/assets/ts/core/media/audioSpeechFeatures.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clamp01 } from '@core/media/audioCaptureSupport.ts';

interface AudioSpeechFeatureInput {
    samples: Float32Array;
    frequencyData: Uint8Array<ArrayBuffer>;
    sampleRate: number;
}

interface AudioSpeechFeatures {
    rms: number;
    peak: number;
    crestFactor: number;
    zeroCrossingRate: number;
    voiceBandRatio: number;
    lowBandRatio: number;
    highBandRatio: number;
    spectralCentroidHz: number;
    voiceBandCoverage: number;
    voiceBandPeakRatio: number;
    periodicity: number;
}

const VOICE_BANDS: readonly [number, number][] = Object.freeze([
    [120, 300],
    [300, 800],
    [800, 1_800],
    [1_800, 3_500]
]);

const computeTimeFeatures = (samples: Float32Array): Pick<AudioSpeechFeatures, 'rms' | 'peak' | 'crestFactor' | 'zeroCrossingRate'> => {
    if (samples.length < 1) {
        return { rms: 0, peak: 0, crestFactor: 0, zeroCrossingRate: 0 };
    }
    let sumSquares = 0;
    let peak = 0;
    let crossings = 0;
    let previous = samples[0] ?? 0;
    for (let index = 0; index < samples.length; index += 1) {
        const sample = samples[index] ?? 0;
        const absolute = Math.abs(sample);
        peak = Math.max(peak, absolute);
        sumSquares += sample * sample;
        if (index > 0 && ((sample >= 0 && previous < 0) || (sample < 0 && previous >= 0))) {
            crossings += 1;
        }
        previous = sample;
    }
    const rms = clamp01(Math.sqrt(sumSquares / samples.length));
    const crestFactor = rms > 0 ? peak / rms : 0;
    const zeroCrossingRate = samples.length > 1 ? crossings / (samples.length - 1) : 0;
    return { rms, peak: clamp01(peak), crestFactor, zeroCrossingRate };
};

const inRange = (frequencyHz: number, lowHz: number, highHz: number): boolean => frequencyHz >= lowHz && frequencyHz < highHz;

const computeSpectralFeatures = (frequencyData: Uint8Array<ArrayBuffer>, sampleRate: number): Pick<AudioSpeechFeatures, 'voiceBandRatio' | 'lowBandRatio' | 'highBandRatio' | 'spectralCentroidHz' | 'voiceBandCoverage' | 'voiceBandPeakRatio'> => {
    if (frequencyData.length < 1 || !Number.isFinite(sampleRate) || sampleRate <= 0) {
        return { voiceBandRatio: 0, lowBandRatio: 0, highBandRatio: 0, spectralCentroidHz: 0, voiceBandCoverage: 0, voiceBandPeakRatio: 0 };
    }
    const nyquistHz = sampleRate / 2;
    const binHz = nyquistHz / frequencyData.length;
    let totalEnergy = 0;
    let voiceEnergy = 0;
    let lowEnergy = 0;
    let highEnergy = 0;
    let weightedFrequency = 0;
    const bandEnergy = VOICE_BANDS.map(() => 0);
    for (let index = 1; index < frequencyData.length; index += 1) {
        const magnitude = (frequencyData[index] ?? 0) / 255;
        const energy = magnitude * magnitude;
        if (energy <= 0) {
            continue;
        }
        const frequencyHz = index * binHz;
        totalEnergy += energy;
        weightedFrequency += frequencyHz * energy;
        if (inRange(frequencyHz, 100, 3_800)) {
            voiceEnergy += energy;
        }
        if (frequencyHz < 170) {
            lowEnergy += energy;
        }
        if (frequencyHz >= 4_000) {
            highEnergy += energy;
        }
        for (let bandIndex = 0; bandIndex < VOICE_BANDS.length; bandIndex += 1) {
            const band = VOICE_BANDS[bandIndex];
            if (band && inRange(frequencyHz, band[0], band[1])) {
                bandEnergy[bandIndex] = (bandEnergy[bandIndex] ?? 0) + energy;
            }
        }
    }
    if (totalEnergy <= 0) {
        return { voiceBandRatio: 0, lowBandRatio: 0, highBandRatio: 0, spectralCentroidHz: 0, voiceBandCoverage: 0, voiceBandPeakRatio: 0 };
    }
    const coverageThreshold = voiceEnergy * 0.04;
    const coveredBands = bandEnergy.filter((energy) => energy >= coverageThreshold).length;
    const peakVoiceBandEnergy = bandEnergy.reduce((current, energy) => Math.max(current, energy), 0);
    return {
        voiceBandRatio: clamp01(voiceEnergy / totalEnergy),
        lowBandRatio: clamp01(lowEnergy / totalEnergy),
        highBandRatio: clamp01(highEnergy / totalEnergy),
        spectralCentroidHz: weightedFrequency / totalEnergy,
        voiceBandCoverage: coveredBands / VOICE_BANDS.length,
        voiceBandPeakRatio: voiceEnergy > 0 ? clamp01(peakVoiceBandEnergy / voiceEnergy) : 0
    };
};

const computePeriodicity = (samples: Float32Array, sampleRate: number, rms: number): number => {
    if (samples.length < 64 || rms < 0.006 || !Number.isFinite(sampleRate) || sampleRate <= 0) {
        return 0;
    }
    let mean = 0;
    for (const sample of samples) {
        mean += sample;
    }
    mean /= samples.length;
    let totalEnergy = 0;
    for (const sample of samples) {
        const centered = sample - mean;
        totalEnergy += centered * centered;
    }
    if (totalEnergy <= 0) {
        return 0;
    }
    const minLag = Math.max(1, Math.floor(sampleRate / 320));
    const maxLag = Math.min(samples.length - 2, Math.ceil(sampleRate / 70));
    let best = 0;
    for (let lag = minLag; lag <= maxLag; lag += 4) {
        let correlation = 0;
        for (let index = 0; index + lag < samples.length; index += 1) {
            correlation += ((samples[index] ?? 0) - mean) * ((samples[index + lag] ?? 0) - mean);
        }
        best = Math.max(best, correlation / totalEnergy);
    }
    return clamp01(best);
};

const extractAudioSpeechFeatures = (input: AudioSpeechFeatureInput): AudioSpeechFeatures => {
    const timeFeatures = computeTimeFeatures(input.samples);
    const spectralFeatures = computeSpectralFeatures(input.frequencyData, input.sampleRate);
    return {
        ...timeFeatures,
        ...spectralFeatures,
        periodicity: computePeriodicity(input.samples, input.sampleRate, timeFeatures.rms)
    };
};

export { extractAudioSpeechFeatures };
export type { AudioSpeechFeatureInput, AudioSpeechFeatures };
