/* SoAI - Chat voice call UI state controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallUiStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { VoiceCallModalUiController } from '@pages/chat/controllers/voicecall/VoiceCallModalUiController.ts';
import { VoiceCallThinkingChimeController } from '@pages/chat/controllers/voicecall/VoiceCallThinkingChimeController.ts';
import type { VoiceCallUiStatus } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

interface VoiceCallUiStateControllerOptions {
    isRuntimeActive(): boolean;
    onEndRequested(): void;
    onPauseRequested(): void;
    onModalClosed(): void;
}

class VoiceCallUiStateController {
    #modalUi: VoiceCallModalUiController;
    #thinkingChime = new VoiceCallThinkingChimeController();
    #isRuntimeActive: () => boolean;
    #paused = false;
    #status: VoiceCallUiStatus = 'idle';
    #prePauseStatus: VoiceCallUiStatus = 'idle';
    #level = 0;
    #userTranscript: string | null = null;
    #assistantCaption: string | null = null;
    #assistantCaptionSequence = 0;
    #errorText: string | null = null;

    constructor(options: VoiceCallUiStateControllerOptions) {
        this.#isRuntimeActive = options.isRuntimeActive;
        this.#modalUi = new VoiceCallModalUiController({
            onEndRequested: () => options.onEndRequested(),
            onPauseRequested: () => options.onPauseRequested(),
            onModalClosed: () => options.onModalClosed()
        });
    }

    open(): void {
        this.#modalUi.open();
        this.emit();
    }

    close(): void {
        this.#modalUi.close();
    }

    dispose(): void {
        this.#thinkingChime.dispose();
        this.#modalUi.dispose();
    }

    reset(): void {
        this.#thinkingChime.stop();
        this.#status = 'idle';
        this.#prePauseStatus = 'idle';
        this.#userTranscript = null;
        this.#assistantCaption = null;
        this.#assistantCaptionSequence = 0;
        this.#errorText = null;
        this.#level = 0;
    }

    setLevel(level: number): void {
        this.#level = Math.max(0, Math.min(1, level));
        this.emit();
    }

    setStatus(status: VoiceCallUiStatus, errorText: string | null): void {
        if (status !== 'paused') {
            this.#prePauseStatus = status;
        }
        if (this.#paused && status !== 'paused' && status !== 'error') {
            this.#errorText = errorText;
            this.emit();
            return;
        }
        this.#status = status;
        this.#errorText = errorText;
        if (status === 'assistantThinking') {
            this.#thinkingChime.start();
        } else {
            this.#thinkingChime.stop();
        }
        this.emit();
    }

    setUserTranscript(transcript: string): void {
        this.#userTranscript = transcript;
        this.#assistantCaption = null;
        this.#assistantCaptionSequence += 1;
        this.emit();
    }

    clearAssistantCaption(): void {
        if (this.#assistantCaption === null) {
            return;
        }
        this.#assistantCaption = null;
        this.#assistantCaptionSequence += 1;
        this.emit();
    }

    setAssistantCaption(transcript: string): void {
        this.#assistantCaption = transcript;
        this.#assistantCaptionSequence += 1;
        this.emit();
    }

    isAssistantResponseStatus(): boolean {
        return this.#status === 'assistantThinking' || this.#status === 'assistantSpeaking';
    }

    isErrorStatus(): boolean {
        return this.#status === 'error';
    }

    resumePreviousStatus(): void {
        const status = this.#prePauseStatus === 'paused' ? 'listening' : this.#prePauseStatus;
        this.setStatus(status, null);
    }

    setPaused(paused: boolean): void {
        this.#paused = paused;
    }

    emit(): void {
        this.#modalUi.update({
            status: this.#status,
            active: this.#isRuntimeActive(),
            paused: this.#paused,
            level: this.#level,
            transcript: {
                userText: this.#userTranscript,
                assistantText: this.#assistantCaption,
                assistantSequence: this.#assistantCaptionSequence
            },
            errorText: this.#errorText
        });
    }
}

export { VoiceCallUiStateController };
