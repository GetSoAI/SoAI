/* SoAI - Shared browser media cleanup helpers [frontend/assets/ts/core/media/mediaCleanup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

const stopMediaStreamTracks = (stream: MediaStream | null): void => {
    if (!stream) {
        return;
    }
    for (const track of stream.getTracks()) {
        track.stop();
    }
};

const closeAudioContextSafe = async (audioContext: AudioContext | null, context: string): Promise<void> => {
    if (!audioContext) {
        return;
    }
    try {
        await audioContext.close();
    } catch (error) {
        errorHandler.warn('MediaCleanup', `Failed to close AudioContext (${context})`, ensureError(error));
    }
};

export { closeAudioContextSafe, stopMediaStreamTracks };
