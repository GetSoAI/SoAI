/* SoAI - Shared browser media capture error classification [frontend/assets/ts/core/media/mediaCaptureErrors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type MediaCaptureFailure = 'permission' | 'missing_device' | 'busy_device' | 'insecure_context' | 'unknown';

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

export { classifyMediaCaptureError };
export type { MediaCaptureFailure };
