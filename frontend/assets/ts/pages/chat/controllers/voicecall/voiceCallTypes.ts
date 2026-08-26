/* SoAI - Chat page voice call types [frontend/assets/ts/pages/chat/controllers/voicecall/voiceCallTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CapturedAudioUtterance } from '@core/media/audioCaptureSupport.ts';
import type { ApiClient } from '@core/api/service.ts';
import type { OpenAiAudioSpeechSessionCallbacks, OpenAiAudioSpeechSessionClient, OpenAiAudioSpeechSessionPayload } from '@core/api/endpoints/openaiWsAudioSpeechSession.ts';
import type { VoiceCallRuntimeAssets } from '@core/media/voiceCallRuntimeAssets.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatContentSegment, ChatMessage, ChatStreamService, MessageSegment } from '@features/chat/public.ts';
import type { QueuedSendGuardContext, QueuedSendGuardResult, QueuedSendOutcome } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

type StopReason = 'user' | 'disabled' | 'hide' | 'modal';

type VoiceCallUiStatus = 'idle' | 'connecting' | 'listening' | 'speaking' | 'transcribing' | 'assistantThinking' | 'assistantSpeaking' | 'paused' | 'error';

interface VoiceCallTranscriptSnapshot {
    userText: string | null;
    assistantText: string | null;
    assistantSequence: number;
}

interface VoiceCallUiSnapshot {
    status: VoiceCallUiStatus;
    active: boolean;
    paused: boolean;
    level: number;
    transcript: VoiceCallTranscriptSnapshot;
    errorText: string | null;
}

interface VoiceCallAudioFrame {
    samples: Float32Array;
    frequencyData: Uint8Array<ArrayBuffer>;
    sampleRate: number;
    nowMs: number;
}

interface VoiceCallTtsSettings {
    model: string;
    voice: string | null;
    speed: number;
}

interface VoiceCallSpeechPlaybackHost extends PageFeedbackOwnerHost {
    speechSessionFactory: {
        create(payload: OpenAiAudioSpeechSessionPayload, callbacks: OpenAiAudioSpeechSessionCallbacks): Promise<OpenAiAudioSpeechSessionClient>;
    };
    isUserSpeechConfirmed(): boolean;
    onSegmentPlaybackStart(text: string): void;
    onAssistantSpeechStateChange(speaking: boolean): void;
    onSpeechQueueDrained(): void;
    onPlaybackFailure(error: Error): void;
}

interface VoiceCallSpeechSegment {
    requestKey: string;
    segmentSequence: number;
    text: string;
}

interface VoiceCallControllerHost extends PageFeedbackOwnerHost {
    apiClient: ApiClient;
    runtimeAssets: VoiceCallRuntimeAssets;
    chatStreamService: ChatStreamService;
    isConversationStreaming(conversationId: string): boolean;
    interruptStreaming(conversationId: string, reason?: string): void;
    waitForConversationIdle(conversationId: string, signal: AbortSignal): Promise<void>;
    resolveMessageContentSegments(message: ChatMessage): MessageSegment[];
    resolveAssistantSpeechText(segments: MessageSegment[]): string;
    cancelAudioRecording(): void;
    getCurrentConversationId(): string | null;
    getCurrentModel(): string | null;
    sendVoiceMessage(text: string, attachmentContent: readonly ChatContentSegment[], signal: AbortSignal, beforeSend: (context: QueuedSendGuardContext) => QueuedSendGuardResult): Promise<QueuedSendOutcome>;
    updateCallButtonState(active: boolean): void;
    resolveTtsSettings(): VoiceCallTtsSettings;
    resolveSttModel(): string;
}

type VoiceCallUtterance = CapturedAudioUtterance;

export type { StopReason, VoiceCallAudioFrame, VoiceCallSpeechPlaybackHost, VoiceCallSpeechSegment, VoiceCallTtsSettings, VoiceCallControllerHost, VoiceCallTranscriptSnapshot, VoiceCallUiSnapshot, VoiceCallUiStatus, VoiceCallUtterance };
