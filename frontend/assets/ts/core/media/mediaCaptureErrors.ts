/* SoAI - Shared browser media capture error classification [frontend/assets/ts/core/media/mediaCaptureErrors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type MediaCaptureFailure = 'permission' | 'missing_device' | 'busy_device' | 'insecure_context' | 'unknown';

type AudioCaptureFailureType = MediaCaptureFailure | 'capture_unsupported' | 'audio_context_unavailable' | 'recording_unavailable' | 'recording_failed';

class AudioCaptureFailure extends Error {
    readonly failureType: AudioCaptureFailureType;

    constructor(failureType: AudioCaptureFailureType, cause: Error | null = null) {
        super(cause ? `Audio capture failed (${failureType}): ${cause.message}` : `Audio capture failed (${failureType})`, cause ? { cause } : undefined);
        this.name = 'AudioCaptureFailure';
        this.failureType = failureType;
    }
}

const classifyMediaCaptureError = (error: Error): MediaCaptureFailure => {
    switch (error.name) {
        case 'NotAllowedError':
        case 'PermissionDeniedError':
            return 'permission';
        case 'NotFoundError':
        case 'DevicesNotFoundError':
            return 'missing_device';
        case 'NotReadableError':
        case 'TrackStartError':
            return 'busy_device';
        case 'SecurityError':
            return 'insecure_context';
        default:
            return 'unknown';
    }
};

const toAudioCaptureFailure = (error: Error, unclassifiedType: AudioCaptureFailureType = 'unknown'): AudioCaptureFailure => {
    if (error instanceof AudioCaptureFailure) {
        return error;
    }
    const classified = classifyMediaCaptureError(error);
    return new AudioCaptureFailure(classified === 'unknown' ? unclassifiedType : classified, error);
};

export { AudioCaptureFailure, classifyMediaCaptureError, toAudioCaptureFailure };
export type { AudioCaptureFailureType, MediaCaptureFailure };
