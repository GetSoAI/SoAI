/* SoAI - Chat voice recording, speech, and call lifecycle ownership [frontend/assets/ts/pages/chat/controllers/chatpage/voice/ChatVoiceSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AudioRecordingSnapshot, AudioRecordingTerminalOutcome, AudioRecordingTimerHost, ChatAudioManager, ChatStreamTerminalUpdate, ChatTtsManager, ComposerDraftSurfaceSnapshot } from '@features/chat/public.ts';
import type { GeometryPoint } from '@core/layout/elementGeometry.ts';
import type { QueueConversationInputOptions, ConversationInputComposerOutcome } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';
import { PushToTalkSession } from '@pages/chat/controllers/chatpage/voice/PushToTalkSession.ts';
import type { VoiceCallController } from '@pages/chat/controllers/voicecall/VoiceCallController.ts';

interface PushToTalkActivation {
    button: HTMLButtonElement;
    start: GeometryPoint;
    lifecycleSignal: AbortSignal;
    timers: AudioRecordingTimerHost;
    conversationId: string | null;
    modelId: string | null;
    draftSnapshot: ComposerDraftSurfaceSnapshot;
    getConversationId(): string | null;
    getModelId(): string | null;
    matchesDraftSurface(snapshot: ComposerDraftSurfaceSnapshot, adoptedConversationId?: string): boolean;
    captureDraftSurface(): ComposerDraftSurfaceSnapshot;
    insertTranscript(text: string): void;
    queueInput(options: QueueConversationInputOptions): Promise<ConversationInputComposerOutcome>;
    present(snapshot: AudioRecordingSnapshot): void;
}

class ChatVoiceSession {
    #audio: ChatAudioManager | null = null;
    #speech: ChatTtsManager | null = null;
    #call: VoiceCallController | null = null;
    #pushToTalk: PushToTalkSession | null = null;

    initializeAudio(manager: ChatAudioManager): void {
        if (this.#audio) {
            manager.dispose();
            return;
        }
        this.#audio = manager;
    }

    initializeSpeech(manager: ChatTtsManager): void {
        if (this.#speech) {
            manager.dispose();
            return;
        }
        this.#speech = manager;
    }

    async initializeCall(controller: VoiceCallController): Promise<void> {
        if (this.#call) {
            await controller.dispose();
            return;
        }
        this.#call = controller;
    }

    hasAudio(): boolean {
        return this.#audio !== null;
    }

    hasSpeech(): boolean {
        return this.#speech !== null;
    }

    hasCall(): boolean {
        return this.#call !== null;
    }

    toggleRecording(): void {
        if (this.#pushToTalk) return;
        this.#requireAudio().toggleRecording();
    }

    cancelRecording(): void {
        if (this.#pushToTalk) {
            this.#pushToTalk.cancel(false);
            return;
        }
        this.#audio?.cancelRecording();
    }

    canStartPushToTalk(): boolean {
        return this.#pushToTalk === null && this.#audio?.state === 'idle';
    }

    beginPushToTalk(activation: PushToTalkActivation): PushToTalkSession | null {
        if (!this.canStartPushToTalk()) return null;
        const session = new PushToTalkSession({
            ...activation,
            audio: this.#requireAudio(),
            onFinished: (finished) => {
                if (this.#pushToTalk === finished) this.#pushToTalk = null;
            }
        });
        this.#pushToTalk = session;
        return session;
    }

    handleAudioSnapshot(snapshot: AudioRecordingSnapshot, present: (snapshot: AudioRecordingSnapshot) => void): void {
        if (this.#pushToTalk?.handleAudioSnapshot(snapshot) === true) return;
        present(snapshot);
    }

    handleAudioTerminal(outcome: AudioRecordingTerminalOutcome, insertDictation: (text: string) => void): void {
        if (this.#pushToTalk?.handleTerminal(outcome) === true) return;
        if (outcome.intent === 'dictation' && outcome.status === 'transcript') insertDictation(outcome.text);
    }

    async stopCallBeforeRecording(): Promise<void> {
        await this.#call?.stop('user');
    }

    toggleCall(run: (task: () => Promise<void>) => void): void {
        const call = this.#requireCall();
        if (!call.isActive()) {
            const speech = this.#requireSpeech();
            speech.stop();
            speech.primePlayback();
        }
        run(() => call.toggle());
    }

    isCallActive(): boolean {
        return this.#call?.isActive() === true;
    }

    async stopCall(reason: Parameters<VoiceCallController['stop']>[0]): Promise<void> {
        await this.#call?.stop(reason);
    }

    handleConversationChanged(conversationId: string | null): void {
        this.#pushToTalk?.handleConversationChanged(conversationId);
        this.#call?.handleConversationChanged(conversationId);
    }

    handleStreamTerminalized(update: ChatStreamTerminalUpdate): void {
        this.#call?.handleStreamTerminalized(update);
    }

    async speakText(...inputArguments: Parameters<ChatTtsManager['speakText']>): Promise<void> {
        await this.#requireSpeech().speakText(...inputArguments);
    }

    stopSpeaking(): void {
        this.#speech?.stop();
    }

    disposeAudio(): void {
        this.#pushToTalk?.cancel(false);
        this.#pushToTalk = null;
        this.#audio?.dispose();
        this.#audio = null;
    }

    async dispose(): Promise<void> {
        await this.#call?.dispose();
        this.#call = null;
        this.#pushToTalk?.cancel(false);
        this.#pushToTalk = null;
        this.#audio?.dispose();
        this.#audio = null;
        this.#speech?.dispose();
        this.#speech = null;
    }

    #requireAudio(): ChatAudioManager {
        if (!this.#audio) throw new Error('Chat audio manager is not initialized');
        return this.#audio;
    }

    #requireSpeech(): ChatTtsManager {
        if (!this.#speech) throw new Error('Chat TTS manager is not initialized');
        return this.#speech;
    }

    #requireCall(): VoiceCallController {
        if (!this.#call) throw new Error('Chat voice call controller is not initialized');
        return this.#call;
    }
}

export { ChatVoiceSession };
export type { PushToTalkActivation };
export interface ChatVoiceSessionHost {
    voiceSession: ChatVoiceSession;
}
