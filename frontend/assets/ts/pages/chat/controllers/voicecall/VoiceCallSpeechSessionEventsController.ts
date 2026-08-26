/* SoAI - Voice call speech session event controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallSpeechSessionEventsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { VoiceCallAudioSegmentSchedulerController } from '@pages/chat/controllers/voicecall/VoiceCallAudioSegmentSchedulerController.ts';
import { VoiceCallSpeechSessionAudioAssemblyManager, type VoiceCallSpeechSegmentAudioAssembly } from '@pages/chat/controllers/voicecall/VoiceCallSpeechSessionAudioAssemblyManager.ts';
import type { VoiceCallSpeechSegment } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

interface VoiceCallSpeechSessionEventsHost {
    isGenerationActive(generation: number): boolean;
    isActive(): boolean;
    setAssistantAudioActive(active: boolean): void;
    setAssistantSpeaking(speaking: boolean): void;
    onSegmentPlaybackStart(text: string): void;
    onPlaybackFailure(error: Error, generation: number): void;
    syncCompletion(): void;
}

class VoiceCallSpeechSessionEventsController {
    readonly #host: VoiceCallSpeechSessionEventsHost;
    readonly #scheduler: VoiceCallAudioSegmentSchedulerController;
    #chunksBySegment = new Map<number, VoiceCallSpeechSegmentAudioAssembly>();
    #completedBytesBySegment = new Map<number, Uint8Array>();
    #textBySegment = new Map<number, string>();
    #startedSegments = new Set<number>();
    #schedulingSegments = new Set<string>();
    #nextSegmentSequenceToSchedule = 0;
    #schedulingDrainActive = false;
    #resetEpoch = 0;

    constructor(host: VoiceCallSpeechSessionEventsHost) {
        this.#host = host;
        this.#scheduler = new VoiceCallAudioSegmentSchedulerController({
            isGenerationActive: (generation) => this.#host.isGenerationActive(generation),
            onSegmentStarted: (segmentSequence) => this.#handleScheduledSegmentStarted(segmentSequence),
            onSegmentCompleted: (segmentSequence) => this.#handleScheduledSegmentCompleted(segmentSequence)
        });
    }

    hasPendingAudio(): boolean {
        return this.#chunksBySegment.size > 0 || this.#completedBytesBySegment.size > 0 || this.#schedulingSegments.size > 0 || this.#scheduler.hasScheduledAudio();
    }

    hasStarted(segmentSequence: number): boolean {
        return this.#startedSegments.has(segmentSequence);
    }

    rememberSegment(segment: VoiceCallSpeechSegment): void {
        this.#textBySegment.set(segment.segmentSequence, segment.text);
    }

    handleChunk(segmentSequence: number, chunkSequence: number, chunkBase64: string, generation: number): void {
        if (!this.#host.isGenerationActive(generation)) {
            return;
        }
        const assembly = this.#chunksBySegment.get(segmentSequence) ?? VoiceCallSpeechSessionAudioAssemblyManager.createAssembly();
        if (!VoiceCallSpeechSessionAudioAssemblyManager.appendChunk(assembly, chunkSequence, chunkBase64)) {
            this.#host.onPlaybackFailure(new Error('Speech session chunk sequence is out of order'), generation);
            return;
        }
        this.#chunksBySegment.set(segmentSequence, assembly);
    }

    handleSegmentCompleted(segmentSequence: number, generation: number): void {
        const assembly = this.#chunksBySegment.get(segmentSequence);
        this.#chunksBySegment.delete(segmentSequence);
        if (!assembly || assembly.chunks.length === 0 || !this.#host.isGenerationActive(generation)) {
            return;
        }
        const bytes = VoiceCallSpeechSessionAudioAssemblyManager.concatenateChunks(assembly.chunks);
        this.#completedBytesBySegment.set(segmentSequence, bytes);
        void this.#drainCompletedSegments(generation).catch((error) => {
            this.#host.onPlaybackFailure(ensureError(error), generation);
        });
        this.#host.setAssistantSpeaking(true);
    }

    reset(): void {
        this.#chunksBySegment.clear();
        this.#completedBytesBySegment.clear();
        this.#textBySegment.clear();
        this.#startedSegments.clear();
        this.#schedulingSegments.clear();
        this.#nextSegmentSequenceToSchedule = 0;
        this.#schedulingDrainActive = false;
        this.#resetEpoch += 1;
        this.#scheduler.cancel();
    }

    async dispose(): Promise<void> {
        this.reset();
        await this.#scheduler.dispose();
    }

    #handleScheduledSegmentStarted(segmentSequence: number): void {
        if (!this.#host.isActive()) {
            return;
        }
        this.#startedSegments.add(segmentSequence);
        this.#host.setAssistantAudioActive(true);
        this.#host.setAssistantSpeaking(true);
        const text = this.#textBySegment.get(segmentSequence);
        if (text) {
            this.#host.onSegmentPlaybackStart(text);
        }
    }

    #handleScheduledSegmentCompleted(segmentSequence: number): void {
        this.#textBySegment.delete(segmentSequence);
        if (!this.hasPendingAudio()) {
            this.#host.setAssistantAudioActive(false);
        }
        this.#host.syncCompletion();
    }

    async #drainCompletedSegments(generation: number): Promise<void> {
        if (this.#schedulingDrainActive) {
            return;
        }
        this.#schedulingDrainActive = true;
        const resetEpoch = this.#resetEpoch;
        try {
            while (this.#host.isGenerationActive(generation) && resetEpoch === this.#resetEpoch) {
                const segmentSequence = this.#nextSegmentSequenceToSchedule;
                const bytes = this.#completedBytesBySegment.get(segmentSequence);
                if (bytes === undefined) {
                    return;
                }
                this.#completedBytesBySegment.delete(segmentSequence);
                const schedulingKey = buildSchedulingSegmentKey(generation, segmentSequence);
                this.#schedulingSegments.add(schedulingKey);
                try {
                    await this.#scheduler.scheduleSegment(segmentSequence, bytes, generation);
                } finally {
                    this.#schedulingSegments.delete(schedulingKey);
                }
                if (!this.#host.isGenerationActive(generation) || resetEpoch !== this.#resetEpoch) {
                    return;
                }
                this.#nextSegmentSequenceToSchedule += 1;
            }
        } finally {
            if (resetEpoch === this.#resetEpoch) {
                this.#schedulingDrainActive = false;
                this.#host.syncCompletion();
            }
        }
    }
}

const buildSchedulingSegmentKey = (generation: number, segmentSequence: number): string => {
    return `${String(generation)}\n${String(segmentSequence)}`;
};

export { VoiceCallSpeechSessionEventsController };
