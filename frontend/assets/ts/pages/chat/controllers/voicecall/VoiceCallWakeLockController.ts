/* SoAI - Chat voice call wake lock controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallWakeLockController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

class VoiceCallWakeLockController {
    #wakeLock: WakeLockSentinel | null = null;
    #generation = 0;

    async start(): Promise<void> {
        if (this.#wakeLock) {
            return;
        }
        if (!('wakeLock' in navigator) || !navigator.wakeLock) {
            return;
        }
        try {
            const generation = this.#generation + 1;
            this.#generation = generation;
            const sentinel = await navigator.wakeLock.request('screen');
            if (generation !== this.#generation || this.#wakeLock) {
                await this.#releaseSentinel(sentinel);
                return;
            }
            this.#wakeLock = sentinel;
        } catch (error) {
            errorHandler.warn('VoiceCallWakeLockController', 'Wake lock unavailable', ensureError(error));
        }
    }

    async release(): Promise<void> {
        this.#generation += 1;
        const sentinel = this.#wakeLock;
        this.#wakeLock = null;
        if (!sentinel) {
            return;
        }
        await this.#releaseSentinel(sentinel);
    }

    async #releaseSentinel(sentinel: WakeLockSentinel): Promise<void> {
        try {
            await sentinel.release();
        } catch (error) {
            errorHandler.warn('VoiceCallWakeLockController', 'Failed to release wake lock', ensureError(error));
        }
    }
}

export { VoiceCallWakeLockController };
