/* SoAI - Shared UI sound contracts [frontend/assets/ts/core/ui/sound/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

type SoundEffectName = 'notificationSuccess' | 'notificationWarning' | 'notificationDanger' | 'microphoneOpen' | 'microphoneClose' | 'voiceCallThinking';

type SoundToneSpec = Readonly<{
    offsetS: number;
    oscType: OscillatorType;
    startHz: number;
    endHz?: number;
    durationS: number;
    peakGain: number;
}>;

type SoundEffectPreferences = Readonly<{
    getSoundEffects: () => boolean;
}>;

interface SoundEffectStoragePreferences {
    getSoundEffects: () => JsonValue;
}

export type { SoundEffectName, SoundEffectPreferences, SoundEffectStoragePreferences, SoundToneSpec };
