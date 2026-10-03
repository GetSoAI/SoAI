/* SoAI - Chat audio recording state contracts [frontend/assets/ts/features/chat/audio/audioRecordingTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type AudioState = 'idle' | 'requesting' | 'recording' | 'processing';
type ActiveAudioState = Exclude<AudioState, 'idle'>;
type AudioRecordingIntent = 'dictation' | 'push-to-talk';
type AudioRecordingPresentation = 'default' | 'ptt-release-to-send' | 'ptt-release-to-cancel' | 'ptt-review' | 'ptt-sending' | 'ptt-queued' | 'ptt-cancelled';

type AudioRecordingTerminalOutcome = { status: 'transcript'; sessionId: number; intent: AudioRecordingIntent; text: string } | { status: 'empty'; sessionId: number; intent: AudioRecordingIntent } | { status: 'cancelled'; sessionId: number; intent: AudioRecordingIntent } | { status: 'failed'; sessionId: number; intent: AudioRecordingIntent; error: Error };

interface AudioRecordingStart {
    sessionId: number;
    started: Promise<boolean>;
}

interface AudioRecordingTimerHost {
    setTimeout(callback: (() => void) | undefined, delay: number): number;
    clearTimeout(timerId: number): void;
}

interface AudioRecordingSnapshot {
    state: AudioState;
    sessionId: number | null;
    intent: AudioRecordingIntent | null;
    presentation: AudioRecordingPresentation;
    elapsedMs: number;
    canCancel: boolean;
    errorText: string | null;
}

export type { ActiveAudioState, AudioRecordingIntent, AudioRecordingPresentation, AudioRecordingSnapshot, AudioRecordingStart, AudioRecordingTerminalOutcome, AudioRecordingTimerHost, AudioState };
