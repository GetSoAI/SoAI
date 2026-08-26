/* SoAI - Chat audio recording state contracts [frontend/assets/ts/features/chat/audio/audioRecordingTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type AudioState = 'idle' | 'requesting' | 'recording' | 'processing';
type ActiveAudioState = Exclude<AudioState, 'idle'>;

interface AudioRecordingSnapshot {
    state: AudioState;
    elapsedMs: number;
    canCancel: boolean;
    errorText: string | null;
}

export type { ActiveAudioState, AudioRecordingSnapshot, AudioState };
