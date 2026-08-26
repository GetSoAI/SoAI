/* SoAI - Voice call Web Audio segment scheduler controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallAudioSegmentSchedulerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveAudioContextConstructor } from '@core/media/audioCaptureSupport.ts';
import { closeAudioContextSafe } from '@core/media/mediaCleanup.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';

const SCHEDULE_LEAD_TIME_SEC = 0.04;

interface VoiceCallAudioSegmentSchedulerControllerHost {
    isGenerationActive(generation: number): boolean;
    onSegmentStarted(segmentSequence: number): void;
    onSegmentCompleted(segmentSequence: number): void;
}

class VoiceCallAudioSegmentSchedulerController {
    readonly #host: VoiceCallAudioSegmentSchedulerControllerHost;
    readonly #timers = new ResourceTracker();
    #audioContext: AudioContext | null = null;
    #nextScheduledTime = 0;
    #sources = new Map<number, AudioBufferSourceNode>();
    #startTimers = new Map<number, number>();
    #completedSegments = new Set<number>();

    constructor(host: VoiceCallAudioSegmentSchedulerControllerHost) {
        this.#host = host;
    }

    hasScheduledAudio(): boolean {
        return this.#sources.size > 0 || this.#startTimers.size > 0;
    }

    async scheduleSegment(segmentSequence: number, bytes: Uint8Array, generation: number): Promise<void> {
        const audioContext = await this.#ensureContext(generation);
        if (!this.#host.isGenerationActive(generation)) {
            return;
        }
        const buffer = await audioContext.decodeAudioData(this.#copyBytes(bytes));
        if (!this.#host.isGenerationActive(generation)) {
            return;
        }
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }
        if (!this.#host.isGenerationActive(generation)) {
            return;
        }
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        const startTime = Math.max(audioContext.currentTime + SCHEDULE_LEAD_TIME_SEC, this.#nextScheduledTime);
        this.#nextScheduledTime = startTime + buffer.duration;
        this.#sources.set(segmentSequence, source);
        this.#trackStart(segmentSequence, startTime, audioContext, generation);
        source.onended = (): void => this.#completeSegment(segmentSequence, generation);
        source.start(startTime);
    }

    cancel(): void {
        for (const timer of this.#startTimers.values()) {
            this.#timers.clearTimeout(timer);
        }
        this.#startTimers.clear();
        for (const source of this.#sources.values()) {
            try {
                source.stop();
            } catch (error) {
                errorHandler.debug('VoiceCallAudioSegmentSchedulerController', 'Scheduled audio source stop failed', ensureError(error));
            }
        }
        this.#sources.clear();
        this.#completedSegments.clear();
        this.#nextScheduledTime = 0;
    }

    async dispose(): Promise<void> {
        this.cancel();
        const audioContext = this.#audioContext;
        this.#audioContext = null;
        this.#timers.cleanup();
        await closeAudioContextSafe(audioContext, 'voice call speech scheduler');
    }

    async #ensureContext(generation: number): Promise<AudioContext> {
        if (this.#audioContext === null) {
            const AudioContextConstructor = resolveAudioContextConstructor();
            this.#audioContext = new AudioContextConstructor();
        }
        const audioContext = this.#audioContext;
        if (audioContext.state === 'suspended' && this.#host.isGenerationActive(generation)) {
            await audioContext.resume();
        }
        return audioContext;
    }

    #trackStart(segmentSequence: number, startTime: number, audioContext: AudioContext, generation: number): void {
        const delayMs = Math.max(0, Math.round((startTime - audioContext.currentTime) * 1000));
        const timer = this.#timers.setTimeout(() => {
            this.#startTimers.delete(segmentSequence);
            if (this.#host.isGenerationActive(generation)) {
                this.#host.onSegmentStarted(segmentSequence);
            }
        }, delayMs);
        this.#startTimers.set(segmentSequence, timer);
    }

    #completeSegment(segmentSequence: number, generation: number): void {
        const timer = this.#startTimers.get(segmentSequence);
        if (timer !== undefined) {
            this.#timers.clearTimeout(timer);
            this.#startTimers.delete(segmentSequence);
        }
        this.#sources.delete(segmentSequence);
        if (!this.#host.isGenerationActive(generation)) {
            return;
        }
        if (this.#completedSegments.has(segmentSequence)) {
            return;
        }
        this.#completedSegments.add(segmentSequence);
        this.#host.onSegmentCompleted(segmentSequence);
    }

    #copyBytes(bytes: Uint8Array): ArrayBuffer {
        const copy = new Uint8Array(bytes.byteLength);
        copy.set(bytes);
        return copy.buffer;
    }
}

export { VoiceCallAudioSegmentSchedulerController };
