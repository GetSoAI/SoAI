/* SoAI - Voice call runtime state controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallRuntimeStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';

class VoiceCallRuntimeStateController {
    readonly #changes = new ChangeNotificationSource();
    readonly #startToken = new SequenceToken();
    #active = false;
    #starting = false;
    #captureReady = false;

    isActive(): boolean {
        return this.#active;
    }

    subscribeStateChanges(listener: () => void): () => boolean {
        return this.#changes.subscribe(listener);
    }

    isStarting(): boolean {
        return this.#starting;
    }

    isRuntimeActive(): boolean {
        return this.#active || this.#starting;
    }

    isCaptureReady(): boolean {
        return this.#captureReady;
    }

    beginStart(): number {
        const token = this.#startToken.next();
        this.#starting = true;
        this.#active = false;
        this.#captureReady = false;
        this.#changes.notify();
        return token;
    }

    finishStarting(token: number): void {
        if (this.#startToken.isActive(token)) {
            this.#starting = false;
            this.#changes.notify();
        }
    }

    markActive(): void {
        this.#active = true;
        this.#captureReady = true;
        this.#changes.notify();
    }

    isStartCurrent(token: number): boolean {
        return this.#starting && this.#startToken.isActive(token);
    }

    isStartTokenActive(token: number): boolean {
        return this.#startToken.isActive(token);
    }

    deactivate(): void {
        this.#starting = false;
        this.#active = false;
        this.#captureReady = false;
        this.#startToken.invalidate();
        this.#changes.notify();
    }
}

export { VoiceCallRuntimeStateController };
