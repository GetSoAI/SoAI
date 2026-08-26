/* SoAI - Chat audio recording snapshot timer controller [frontend/assets/ts/features/chat/audio/AudioRecordingSnapshotController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ActiveAudioState, AudioRecordingSnapshot, AudioState } from '@features/chat/audio/audioRecordingTypes.ts';

interface AudioRecordingSnapshotControllerOptions {
    onSnapshotChange(snapshot: AudioRecordingSnapshot): void;
}

class AudioRecordingSnapshotController {
    #onSnapshotChange: (snapshot: AudioRecordingSnapshot) => void;
    #resources = new ResourceTracker();
    #state: AudioState = 'idle';
    #startedAtMs: number | null = null;
    #elapsedTimer: number | null = null;

    constructor(options: AudioRecordingSnapshotControllerOptions) {
        this.#onSnapshotChange = options.onSnapshotChange;
        this.#emit(null);
    }

    begin(state: ActiveAudioState): void {
        this.#clearElapsedTimer();
        this.#startedAtMs = performance.now();
        this.#state = state;
        this.#syncElapsedTimer();
        this.emit(null);
    }

    setState(state: AudioState): void {
        if (state === 'idle') {
            this.reset();
            return;
        }
        this.#state = state;
        this.#syncElapsedTimer();
        this.emit(null);
    }

    reset(): void {
        this.#clearElapsedTimer();
        this.#startedAtMs = null;
        this.#state = 'idle';
        this.emit(null);
    }

    fail(errorText: string): void {
        this.#clearElapsedTimer();
        this.#startedAtMs = null;
        this.#state = 'idle';
        this.emit(errorText);
    }

    emit(errorText: string | null): void {
        this.#emit(errorText);
    }

    #emit(errorText: string | null): void {
        const startedAtMs = this.#startedAtMs;
        const elapsedMs = startedAtMs === null ? 0 : Math.max(0, Math.round(performance.now() - startedAtMs));
        this.#onSnapshotChange({
            state: this.#state,
            elapsedMs,
            canCancel: this.#state === 'requesting' || this.#state === 'recording' || this.#state === 'processing',
            errorText
        });
    }

    dispose(): void {
        this.reset();
        this.#resources.cleanup();
    }

    #syncElapsedTimer(): void {
        if (this.#state !== 'recording' && this.#state !== 'processing' && this.#state !== 'requesting') {
            this.#clearElapsedTimer();
            return;
        }
        if (this.#elapsedTimer !== null) {
            return;
        }
        this.#elapsedTimer = this.#resources.setInterval(() => this.emit(null), 250);
    }

    #clearElapsedTimer(): void {
        if (this.#elapsedTimer === null) {
            return;
        }
        this.#resources.clearInterval(this.#elapsedTimer);
        this.#elapsedTimer = null;
    }
}

export { AudioRecordingSnapshotController };
export type { AudioRecordingSnapshotControllerOptions };
