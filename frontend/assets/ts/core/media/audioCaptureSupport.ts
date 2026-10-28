/* SoAI - Shared browser audio capture support [frontend/assets/ts/core/media/audioCaptureSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { AudioCaptureFailure, toAudioCaptureFailure } from '@core/media/mediaCaptureErrors.ts';

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

const resolveAudioCaptureFailureMessage = (error: Error): string | null => {
    if (!(error instanceof AudioCaptureFailure)) {
        return null;
    }
    switch (error.failureType) {
        case 'permission':
            return i18n.t('chat.audio.permissionDenied');
        case 'missing_device':
            return i18n.t('chat.audio.noDevice');
        case 'busy_device':
            return i18n.t('chat.audio.deviceBusy');
        case 'insecure_context':
        case 'capture_unsupported':
            return i18n.t('chat.audio.notSupported');
        case 'audio_context_unavailable':
            return i18n.t('chat.voiceCall.audioContextUnavailable');
        case 'recording_unavailable':
            return i18n.t('chat.voiceCall.recordingUnavailable');
        case 'recording_failed':
            return i18n.t('chat.audio.recordingFailed');
        case 'unknown':
            return null;
    }
};

const resolveGetUserMediaError = (error: Error): string => resolveAudioCaptureFailureMessage(toAudioCaptureFailure(error)) ?? i18n.t('chat.audio.initFailed');

export { clamp01, resolveAudioCaptureFailureMessage, resolveAudioContextConstructor, resolveGetUserMediaError };
export type { CapturedAudioUtterance };
