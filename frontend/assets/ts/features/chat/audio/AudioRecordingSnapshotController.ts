/* SoAI - Chat audio recording snapshot timer controller [frontend/assets/ts/features/chat/audio/AudioRecordingSnapshotController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ActiveAudioState, AudioRecordingIntent, AudioRecordingSnapshot, AudioState } from '@features/chat/audio/audioRecordingTypes.ts';

interface AudioRecordingSnapshotControllerOptions {
    onSnapshotChange(snapshot: AudioRecordingSnapshot): void;
}

class AudioRecordingSnapshotController {
    #onSnapshotChange: (snapshot: AudioRecordingSnapshot) => void;
    #resources = new ResourceTracker();
    #state: AudioState = 'idle';
    #startedAtMs: number | null = null;
    #elapsedTimer: number | null = null;
    #sessionId: number | null = null;
    #intent: AudioRecordingIntent | null = null;
    #transcriptionSettling = false;

    constructor(options: AudioRecordingSnapshotControllerOptions) {
        this.#onSnapshotChange = options.onSnapshotChange;
        this.#emit(null);
    }

    begin(state: ActiveAudioState, sessionId: number, intent: AudioRecordingIntent): void {
        this.#clearElapsedTimer();
        this.#startedAtMs = performance.now();
        this.#transcriptionSettling = false;
        this.#state = state;
        this.#sessionId = sessionId;
        this.#intent = intent;
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

    markTranscriptionSettling(): void {
        if (this.#state !== 'processing') return;
        this.#transcriptionSettling = true;
        this.emit(null);
    }

    reset(): void {
        this.#clearElapsedTimer();
        this.#startedAtMs = null;
        this.#transcriptionSettling = false;
        this.#state = 'idle';
        this.#sessionId = null;
        this.#intent = null;
        this.emit(null);
    }

    fail(errorText: string): void {
        this.#clearElapsedTimer();
        this.#startedAtMs = null;
        this.#transcriptionSettling = false;
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
            sessionId: this.#sessionId,
            intent: this.#intent,
            presentation: this.#transcriptionSettling ? 'transcription-settling' : 'default',
            elapsedMs,
            canCancel: !this.#transcriptionSettling && (this.#state === 'requesting' || this.#state === 'recording' || this.#state === 'processing'),
            errorText
        });
    }

    dispose(): void {
        this.reset();
        this.#resources.cleanup();
    }

    #syncElapsedTimer(): void {
        if (this.#state !== 'recording') {
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
