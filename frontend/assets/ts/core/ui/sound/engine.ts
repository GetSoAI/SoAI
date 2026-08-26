/* SoAI - Shared UI engine [frontend/assets/ts/core/ui/sound/engine.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import { hasFunctionProperty, isPlainObject } from '@core/typeGuards.ts';
import { SOUND_EFFECT_PRESETS } from '@core/ui/sound/presets.ts';
import type { SoundEffectName, SoundEffectPreferences, SoundEffectStoragePreferences, SoundToneSpec } from '@core/ui/sound/types.ts';

let soundAudioContext: AudioContext | null = null;
let soundUnlockRegistered = false;
let soundPreferencesCache: SoundEffectPreferences | null = null;

const isSoundEffectStoragePreferences = <T>(value: T): value is T & SoundEffectStoragePreferences => isPlainObject(value) && hasFunctionProperty(value, 'getSoundEffects');

const requireSoundPreferences = (): SoundEffectPreferences => {
    if (soundPreferencesCache) {
        return soundPreferencesCache;
    }
    const storageCandidate = requireStorageService();
    if (!isSoundEffectStoragePreferences(storageCandidate)) {
        throw new TypeError('Storage service must expose a getSoundEffects() method');
    }
    soundPreferencesCache = Object.freeze({
        getSoundEffects: (): boolean => storageCandidate.getSoundEffects() === true
    });
    return soundPreferencesCache;
};

const initializeSoundAudioContext = (): void => {
    if (soundAudioContext) {
        return;
    }
    try {
        soundAudioContext = new AudioContext();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('SoundEffects', 'Initializing sound audio context failed', runtimeError);
        throw runtimeError;
    }
    if (soundAudioContext.state === 'suspended') {
        void soundAudioContext.resume().catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.error('SoundEffects', 'Resuming sound audio context failed', runtimeError);
        });
    }
};

const initializeSoundEffectsUnlock = (): void => {
    if (soundUnlockRegistered) {
        return;
    }
    soundUnlockRegistered = true;
    window.addEventListener('pointerdown', initializeSoundAudioContext, { capture: true, once: true });
    window.addEventListener('keydown', initializeSoundAudioContext, { capture: true, once: true });
    window.addEventListener('touchstart', initializeSoundAudioContext, { capture: true, once: true });
};

const playTone = (context: AudioContext, startTime: number, spec: SoundToneSpec): void => {
    const osc = context.createOscillator();
    const gain = context.createGain();
    const endTime = startTime + spec.durationS;
    osc.type = spec.oscType;
    osc.frequency.setValueAtTime(spec.startHz, startTime);
    if (spec.endHz !== undefined) {
        osc.frequency.linearRampToValueAtTime(spec.endHz, endTime);
    }
    gain.gain.setValueAtTime(0.0001, startTime);
    gain.gain.exponentialRampToValueAtTime(spec.peakGain, startTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, endTime);
    osc.connect(gain);
    gain.connect(context.destination);
    osc.start(startTime);
    osc.stop(endTime);
    osc.onended = (): void => {
        osc.disconnect();
        gain.disconnect();
    };
};

const playSoundEffectPreset = (context: AudioContext, effect: SoundEffectName): void => {
    const currentTime = context.currentTime;
    SOUND_EFFECT_PRESETS[effect].forEach((tone) => playTone(context, currentTime + tone.offsetS, tone));
};

const resumeAndPlaySoundEffect = (context: AudioContext, effect: SoundEffectName): void => {
    void context
        .resume()
        .then(() => {
            if (context === soundAudioContext && context.state === 'running') {
                playSoundEffectPreset(context, effect);
            }
        })
        .catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.error('SoundEffects', 'Resuming sound audio context failed', runtimeError);
        });
};

const playSoundEffect = (effect: SoundEffectName): void => {
    try {
        if (!requireSoundPreferences().getSoundEffects()) {
            return;
        }
        const context = soundAudioContext;
        if (!context) {
            return;
        }
        if (context.state === 'suspended') {
            resumeAndPlaySoundEffect(context, effect);
            return;
        }
        if (context.state !== 'running') {
            return;
        }
        playSoundEffectPreset(context, effect);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('SoundEffects', 'Playing sound effect failed', runtimeError);
    }
};

export { initializeSoundEffectsUnlock, playSoundEffect };
