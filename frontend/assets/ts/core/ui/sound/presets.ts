/* SoAI - Shared UI presets [frontend/assets/ts/core/ui/sound/presets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SoundEffectName, SoundToneSpec } from '@core/ui/sound/types.ts';

const SOUND_EFFECT_PRESETS: Readonly<Record<SoundEffectName, readonly SoundToneSpec[]>> = Object.freeze({
    notificationSuccess: [
        {
            offsetS: 0,
            oscType: 'sine',
            startHz: 1318,
            durationS: 0.16,
            peakGain: 0.14
        }
    ],
    notificationWarning: [
        {
            offsetS: 0,
            oscType: 'sine',
            startHz: 523,
            durationS: 0.12,
            peakGain: 0.12
        },
        {
            offsetS: 0.08,
            oscType: 'sine',
            startHz: 698,
            durationS: 0.14,
            peakGain: 0.11
        }
    ],
    notificationDanger: [
        {
            offsetS: 0,
            oscType: 'sine',
            startHz: 440,
            durationS: 0.15,
            peakGain: 0.13
        },
        {
            offsetS: 0.11,
            oscType: 'sine',
            startHz: 370,
            durationS: 0.16,
            peakGain: 0.12
        }
    ],
    microphoneOpen: [
        {
            offsetS: 0,
            oscType: 'sine',
            startHz: 587,
            endHz: 880,
            durationS: 0.12,
            peakGain: 0.12
        },
        {
            offsetS: 0.1,
            oscType: 'sine',
            startHz: 988,
            durationS: 0.13,
            peakGain: 0.11
        }
    ],
    microphoneClose: [
        {
            offsetS: 0,
            oscType: 'sine',
            startHz: 880,
            endHz: 660,
            durationS: 0.12,
            peakGain: 0.12
        },
        {
            offsetS: 0.1,
            oscType: 'sine',
            startHz: 523,
            durationS: 0.14,
            peakGain: 0.11
        }
    ],
    voiceCallThinking: [
        {
            offsetS: 0,
            oscType: 'sine',
            startHz: 740,
            durationS: 0.12,
            peakGain: 0.05
        },
        {
            offsetS: 0.11,
            oscType: 'sine',
            startHz: 932,
            durationS: 0.16,
            peakGain: 0.045
        }
    ]
});

export { SOUND_EFFECT_PRESETS };
