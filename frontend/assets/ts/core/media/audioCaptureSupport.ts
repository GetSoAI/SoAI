/* SoAI - Shared browser audio capture support [frontend/assets/ts/core/media/audioCaptureSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';

interface CapturedAudioUtterance {
    blob: Blob;
    mimeType: string;
}

declare const webkitAudioContext: typeof AudioContext | undefined;

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));

const resolveAudioContextConstructor = (): typeof AudioContext => {
    if (typeof AudioContext === 'function') {
        return AudioContext;
    }
    if (typeof webkitAudioContext === 'function') {
        return webkitAudioContext;
    }
    throw new Error(i18n.t('chat.voiceCall.audioContextUnavailable'));
};

const resolveGetUserMediaError = (error: Error): string => {
    const runtimeError = ensureError(error);
    const name = runtimeError.name;
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        return i18n.t('chat.audio.permissionDenied');
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        return i18n.t('chat.audio.noDevice');
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
        return i18n.t('chat.audio.deviceBusy');
    }
    if (name === 'SecurityError') {
        return i18n.t('chat.audio.notSupported');
    }
    return i18n.t('chat.audio.initFailed');
};

export { clamp01, resolveAudioContextConstructor, resolveGetUserMediaError };
export type { CapturedAudioUtterance };
