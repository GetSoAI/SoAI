/* SoAI - Voice call thinking chime timer [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallThinkingChimeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { playSoundEffect } from '@core/ui/sound/engine.ts';

const THINKING_CHIME_DELAY_MS = 5_000;
const THINKING_CHIME_REPEAT_MS = 3_000;

class VoiceCallThinkingChimeController {
    readonly #timers = new ResourceTracker();
    #active = false;
    #delayTimer: number | null = null;
    #repeatTimer: number | null = null;

    start(): void {
        if (this.#active) {
            return;
        }
        this.#active = true;
        this.#delayTimer = this.#timers.setTimeout(() => {
            this.#delayTimer = null;
            this.#playAndRepeat();
        }, THINKING_CHIME_DELAY_MS);
    }

    stop(): void {
        this.#active = false;
        if (this.#delayTimer !== null) {
            this.#timers.clearTimeout(this.#delayTimer);
            this.#delayTimer = null;
        }
        if (this.#repeatTimer !== null) {
            this.#timers.clearInterval(this.#repeatTimer);
            this.#repeatTimer = null;
        }
    }

    dispose(): void {
        this.#active = false;
        this.#timers.cleanup();
        this.#delayTimer = null;
        this.#repeatTimer = null;
    }

    #playAndRepeat(): void {
        if (!this.#active) {
            return;
        }
        playSoundEffect('voiceCallThinking');
        this.#repeatTimer = this.#timers.setInterval(() => {
            if (this.#active) {
                playSoundEffect('voiceCallThinking');
            }
        }, THINKING_CHIME_REPEAT_MS);
    }
}

export { VoiceCallThinkingChimeController };
