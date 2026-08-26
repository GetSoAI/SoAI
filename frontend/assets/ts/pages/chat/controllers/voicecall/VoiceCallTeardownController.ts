/* SoAI - Voice call teardown controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallTeardownController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { VoiceCallAssistantSpeaker } from '@pages/chat/controllers/voicecall/VoiceCallAssistantSpeaker.ts';
import type { VoiceCallAudioCapture } from '@pages/chat/controllers/voicecall/VoiceCallAudioCapture.ts';
import type { VoiceCallTurnManager } from '@pages/chat/controllers/voicecall/VoiceCallTurnManager.ts';
import type { VoiceCallWakeLockController } from '@pages/chat/controllers/voicecall/VoiceCallWakeLockController.ts';

interface VoiceCallTeardownControllerDependencies {
    speaker: VoiceCallAssistantSpeaker;
    turnManager: VoiceCallTurnManager;
    audioCapture: VoiceCallAudioCapture;
    wakeLock: VoiceCallWakeLockController;
    updateCallButtonState(active: boolean): void;
}

class VoiceCallTeardownController {
    readonly #dependencies: VoiceCallTeardownControllerDependencies;

    constructor(dependencies: VoiceCallTeardownControllerDependencies) {
        this.#dependencies = dependencies;
    }

    async perform(): Promise<void> {
        try {
            this.#dependencies.speaker.stop();
        } catch (error) {
            errorHandler.warn('VoiceCallTeardownController', 'Voice call speaker teardown failed', ensureError(error));
        }
        try {
            this.#dependencies.turnManager.abortTranscription();
        } catch (error) {
            errorHandler.warn('VoiceCallTeardownController', 'Voice call transcription teardown failed', ensureError(error));
        }
        try {
            await this.#dependencies.audioCapture.stop();
        } catch (error) {
            errorHandler.warn('VoiceCallTeardownController', 'Voice call audio capture teardown failed', ensureError(error));
        }
        try {
            await this.#dependencies.wakeLock.release();
        } catch (error) {
            errorHandler.warn('VoiceCallTeardownController', 'Voice call wake lock teardown failed', ensureError(error));
        }
        try {
            this.#dependencies.updateCallButtonState(false);
        } catch (error) {
            errorHandler.warn('VoiceCallTeardownController', 'Voice call button teardown failed', ensureError(error));
        }
    }
}

export { VoiceCallTeardownController };
