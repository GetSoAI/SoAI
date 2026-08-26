/* SoAI - Voice call pause orchestration [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallPauseController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface VoiceCallPauseAudioCapture {
    pause(): Promise<void>;
    resume(): Promise<void>;
}

interface VoiceCallPauseSpeaker {
    pause(): void;
    resume(): void;
}

interface VoiceCallPauseUiState {
    setLevel(level: number): void;
    setStatus(status: 'paused' | 'error', errorText: string | null): void;
    resumePreviousStatus(): void;
    setPaused(paused: boolean): void;
}

interface VoiceCallPauseControllerDependencies {
    audioCapture: VoiceCallPauseAudioCapture;
    speaker: VoiceCallPauseSpeaker;
    uiState: VoiceCallPauseUiState;
    isRuntimeActive(): boolean;
    isStarting(): boolean;
    showNotification(message: string, type: NotificationType, duration?: number): void;
}

class VoiceCallPauseController {
    #audioCapture: VoiceCallPauseAudioCapture;
    #speaker: VoiceCallPauseSpeaker;
    #uiState: VoiceCallPauseUiState;
    #isRuntimeActive: () => boolean;
    #isStarting: () => boolean;
    #showNotification: (message: string, type: NotificationType, duration?: number) => void;
    readonly #transitionToken = new SequenceToken();
    #paused = false;
    #desiredPaused = false;
    #capturePaused = false;
    #transitioning = false;

    constructor(dependencies: VoiceCallPauseControllerDependencies) {
        this.#audioCapture = dependencies.audioCapture;
        this.#speaker = dependencies.speaker;
        this.#uiState = dependencies.uiState;
        this.#isRuntimeActive = dependencies.isRuntimeActive;
        this.#isStarting = dependencies.isStarting;
        this.#showNotification = dependencies.showNotification;
    }

    isPaused(): boolean {
        return this.#paused;
    }

    reset(): void {
        this.#transitionToken.invalidate();
        this.#paused = false;
        this.#desiredPaused = false;
        this.#capturePaused = false;
        this.#transitioning = false;
        this.#uiState.setPaused(false);
    }

    async toggle(): Promise<void> {
        if (!this.#canRequestTransition()) {
            return;
        }
        this.#requestPaused(!this.#desiredPaused);
        await this.#syncCapturePausedState();
    }

    async pause(): Promise<void> {
        if (!this.#canRequestTransition() || this.#desiredPaused) {
            return;
        }
        this.#requestPaused(true);
        await this.#syncCapturePausedState();
    }

    async resume(): Promise<void> {
        if (!this.#canRequestTransition() || !this.#desiredPaused) {
            return;
        }
        this.#requestPaused(false);
        await this.#syncCapturePausedState();
    }

    #requestPaused(paused: boolean): void {
        this.#desiredPaused = paused;
        if (paused) {
            this.#applyPausedState(true);
        }
    }

    #applyPausedState(paused: boolean): void {
        if (this.#paused === paused) {
            return;
        }
        this.#paused = paused;
        this.#uiState.setPaused(paused);
        if (paused) {
            this.#speaker.pause();
            this.#uiState.setLevel(0);
            this.#uiState.setStatus('paused', null);
            return;
        }
        this.#speaker.resume();
        this.#uiState.resumePreviousStatus();
    }

    async #syncCapturePausedState(): Promise<void> {
        if (this.#transitioning) {
            return;
        }
        this.#transitioning = true;
        const token = this.#transitionToken.next();
        try {
            while (this.#transitionToken.isActive(token) && this.#canRequestTransition()) {
                const targetPaused = this.#desiredPaused;
                if (targetPaused === this.#capturePaused) {
                    this.#applyPausedState(targetPaused);
                    return;
                }
                if (targetPaused) {
                    await this.#audioCapture.pause();
                    if (!this.#transitionToken.isActive(token)) {
                        return;
                    }
                    this.#capturePaused = true;
                } else {
                    await this.#audioCapture.resume();
                    if (!this.#transitionToken.isActive(token)) {
                        return;
                    }
                    this.#capturePaused = false;
                    this.#applyPausedState(false);
                }
            }
            if (!this.#isRuntimeActive() || this.#isStarting()) {
                this.reset();
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#desiredPaused = false;
            this.#paused = false;
            this.#uiState.setPaused(false);
            this.#capturePaused = false;
            if (!this.#isRuntimeActive()) {
                return;
            }
            errorHandler.warn('VoiceCallPauseController', 'Voice call pause transition failed', runtimeError);
            const failureMessage = i18n.t('chat.voiceCall.pauseFailed');
            this.#uiState.setStatus('error', failureMessage);
            this.#showNotification(failureMessage, 'error');
        } finally {
            if (this.#transitionToken.isActive(token)) {
                this.#transitioning = false;
            }
        }
    }

    #canRequestTransition(): boolean {
        return this.#isRuntimeActive() && !this.#isStarting();
    }
}

export { VoiceCallPauseController };
