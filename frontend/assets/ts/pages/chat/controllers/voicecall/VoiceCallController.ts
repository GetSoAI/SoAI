/* SoAI - Chat page voice call controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { playSoundEffect } from '@core/ui/sound/engine.ts';
import type { ChatStreamTerminalUpdate } from '@features/chat/public.ts';
import { VoiceCallAssistantSpeaker } from '@pages/chat/controllers/voicecall/VoiceCallAssistantSpeaker.ts';
import { VoiceCallAssistantStatusController } from '@pages/chat/controllers/voicecall/VoiceCallAssistantStatusController.ts';
import { VoiceCallAudioCapture } from '@pages/chat/controllers/voicecall/VoiceCallAudioCapture.ts';
import { VoiceCallPauseController } from '@pages/chat/controllers/voicecall/VoiceCallPauseController.ts';
import { VoiceCallRuntimeStateController } from '@pages/chat/controllers/voicecall/VoiceCallRuntimeStateController.ts';
import { VoiceCallTeardownController } from '@pages/chat/controllers/voicecall/VoiceCallTeardownController.ts';
import { VoiceCallTranscriber } from '@pages/chat/controllers/voicecall/VoiceCallTranscriber.ts';
import { VoiceCallTurnManager } from '@pages/chat/controllers/voicecall/VoiceCallTurnManager.ts';
import { VoiceCallUiStateController } from '@pages/chat/controllers/voicecall/VoiceCallUiStateController.ts';
import { VoiceCallWakeLockController } from '@pages/chat/controllers/voicecall/VoiceCallWakeLockController.ts';
import type { StopReason, VoiceCallControllerHost } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';
import { VoiceCallConversationState } from '@pages/chat/controllers/voicecall/VoiceCallConversationState.ts';
import { VoiceCallAssistantSpeechEventManager } from '@pages/chat/controllers/voicecall/VoiceCallAssistantSpeechEventManager.ts';

class VoiceCallController {
    #host: VoiceCallControllerHost;
    readonly #runtimeState = new VoiceCallRuntimeStateController();
    readonly #conversationBinding = new VoiceCallConversationState();
    readonly #speechEvents = new VoiceCallAssistantSpeechEventManager();
    #wakeLock = new VoiceCallWakeLockController();

    #transcriber: VoiceCallTranscriber;
    #speaker: VoiceCallAssistantSpeaker;
    #audioCapture: VoiceCallAudioCapture;
    #uiState: VoiceCallUiStateController;
    #turnManager: VoiceCallTurnManager;
    #pauseController: VoiceCallPauseController;
    #assistantStatus: VoiceCallAssistantStatusController;
    #teardown: VoiceCallTeardownController;
    #speechEventsExit: () => void;

    constructor(host: VoiceCallControllerHost) {
        this.#host = host;
        this.#uiState = new VoiceCallUiStateController({
            isRuntimeActive: () => this.#runtimeState.isRuntimeActive(),
            onEndRequested: () => {
                this.stop('user').catch((error) => {
                    errorHandler.warn('VoiceCallController', 'Voice call end request failed', ensureError(error));
                });
            },
            onPauseRequested: () => {
                this.togglePause().catch((error) => {
                    errorHandler.warn('VoiceCallController', 'Voice call pause request failed', ensureError(error));
                });
            },
            onModalClosed: () => {
                this.stop('modal').catch((error) => {
                    errorHandler.warn('VoiceCallController', 'Voice call modal close handling failed', ensureError(error));
                });
            }
        });
        this.#transcriber = new VoiceCallTranscriber(host.apiClient);
        this.#speaker = new VoiceCallAssistantSpeaker({
            feedback: host.feedback,
            speechSessionFactory: host.apiClient.webui.media.audio.speech.session,
            chatStreamService: host.chatStreamService,
            getCurrentConversationId: () => this.#conversationBinding.get(),
            resolveMessageContentSegments: (message) => host.resolveMessageContentSegments(message),
            resolveAssistantSpeechText: (segments) => host.resolveAssistantSpeechText(segments),
            resolveTtsSettings: () => host.resolveTtsSettings(),
            isUserSpeechConfirmed: () => this.#audioCapture.isUserSpeechConfirmed(),
            onAssistantCaptionSegment: (text) => this.#uiState.setAssistantCaption(text),
            onAssistantSpeechStateChange: (speaking) => this.#speechEvents.speechStateChanged(speaking),
            onAssistantSpeechQueueDrained: () => this.#speechEvents.speechQueueDrained(),
            onAssistantSpeechPlaybackError: () => this.#speechEvents.playbackFailed()
        });
        this.#turnManager = new VoiceCallTurnManager({
            feedback: host.feedback,
            controllerHost: host,
            transcriber: this.#transcriber,
            speaker: this.#speaker,
            isActive: () => this.#runtimeState.isRuntimeActive(),
            setStatus: (status, errorText) => this.#uiState.setStatus(status, errorText),
            setUserTranscript: (text) => this.#uiState.setUserTranscript(text),
            clearAssistantCaption: () => this.#uiState.clearAssistantCaption(),
            stopUnboundConversationChange: () => this.#stopForConversationSwitch(),
            conversationBinding: this.#conversationBinding
        });
        this.#audioCapture = new VoiceCallAudioCapture(
            {
                getAssistantAudioActive: () => this.#speaker.isAssistantAudioActive(),
                isRuntimeReady: () => this.#runtimeState.isCaptureReady(),
                onUserSpeechStart: () => this.#turnManager.handleUserSpeechStart(),
                onUtterance: (utterance) => this.#turnManager.handleUtterance(utterance),
                onLevelChange: (level) => this.#uiState.setLevel(level),
                onError: (error) => this.#handleCaptureError(error)
            },
            host.runtimeAssets
        );
        this.#pauseController = new VoiceCallPauseController({
            audioCapture: this.#audioCapture,
            speaker: this.#speaker,
            uiState: this.#uiState,
            isRuntimeActive: () => this.#runtimeState.isActive(),
            isStarting: () => this.#runtimeState.isStarting(),
            showNotification: (message, type, duration) => host.feedback.show(message, type, duration)
        });
        this.#assistantStatus = new VoiceCallAssistantStatusController({
            turnManager: this.#turnManager,
            uiState: this.#uiState,
            isActive: () => this.#runtimeState.isActive(),
            isPaused: () => this.#pauseController.isPaused()
        });
        this.#speechEventsExit = this.#speechEvents.subscribe({
            speechStateChanged: (speaking) => this.#assistantStatus.handleSpeechStateChange(speaking),
            speechQueueDrained: () => this.#assistantStatus.reconcile(),
            playbackFailed: () => this.#assistantStatus.handlePlaybackError()
        });
        this.#teardown = new VoiceCallTeardownController({
            speaker: this.#speaker,
            turnManager: this.#turnManager,
            audioCapture: this.#audioCapture,
            wakeLock: this.#wakeLock,
            updateCallButtonState: (active) => host.updateCallButtonState(active)
        });
    }

    isActive(): boolean {
        return this.#runtimeState.isActive();
    }

    async toggle(): Promise<void> {
        if (this.#runtimeState.isRuntimeActive()) {
            await this.stop('user');
            return;
        }
        await this.start();
    }

    async start(): Promise<void> {
        if (this.#runtimeState.isRuntimeActive()) {
            return;
        }
        const getUserMedia = navigator?.mediaDevices?.getUserMedia;
        if (typeof getUserMedia !== 'function') {
            this.#host.feedback.show(i18n.t('chat.audio.notSupported'), 'error');
            return;
        }
        const currentModel = this.#host.getCurrentModel();
        if (!toTrimmedString(currentModel)) {
            this.#host.feedback.show(i18n.t('chat.voiceCall.noModelSelected'), 'warning');
            return;
        }
        const token = this.#runtimeState.beginStart();
        this.#pauseController.reset();
        this.#turnManager.bindInitialConversation();
        this.#host.cancelAudioRecording();
        this.#uiState.reset();
        this.#uiState.open();
        this.#uiState.setStatus('connecting', null);
        try {
            await this.#wakeLock.start();
            if (!this.#runtimeState.isStartCurrent(token)) {
                return;
            }
            await this.#audioCapture.start();
            if (!this.#runtimeState.isStartCurrent(token)) {
                await this.#audioCapture.stop();
                return;
            }
            this.#speaker.start();
            this.#pauseController.reset();
            playSoundEffect('microphoneOpen');
            this.#uiState.setStatus('listening', null);
            this.#host.updateCallButtonState(true);
            this.#host.feedback.show(i18n.t('chat.voiceCall.started'), 'success');
            this.#runtimeState.markActive();
        } catch (startError) {
            if (!this.#runtimeState.isStartTokenActive(token)) {
                return;
            }
            this.#host.feedback.handle(ensureError(startError), 'Voice call start failed');
            const failureMessage = i18n.t('chat.voiceCall.failed');
            this.#uiState.setStatus('error', failureMessage);
            this.#host.feedback.show(failureMessage, 'error');
        } finally {
            this.#runtimeState.finishStarting(token);
            if (this.#runtimeState.isStartTokenActive(token) && !this.#runtimeState.isActive()) {
                this.#turnManager.clear();
                await this.#teardown.perform();
            }
        }
    }

    #deactivate(): void {
        this.#runtimeState.deactivate();
        this.#pauseController.reset();
        this.#turnManager.clear();
    }

    #handleCaptureError(error: Error): void {
        const shouldTeardown = this.#runtimeState.isRuntimeActive();
        if (shouldTeardown) {
            this.#deactivate();
        }
        this.#host.feedback.handle(error, 'Voice call capture failed');
        const failureMessage = i18n.t('chat.voiceCall.failed');
        try {
            this.#uiState.setStatus('error', failureMessage);
            this.#host.feedback.show(failureMessage, 'error');
        } finally {
            if (shouldTeardown) {
                void this.#teardown.perform().catch((teardownError) => {
                    errorHandler.warn('VoiceCallController', 'Voice call capture error teardown failed', ensureError(teardownError));
                });
            }
        }
    }

    readonly togglePause = async (): Promise<void> => {
        await this.#pauseController.toggle();
    };

    readonly stop = async (reason: StopReason): Promise<void> => {
        if (!this.#runtimeState.isRuntimeActive()) {
            if (reason !== 'modal') {
                this.#uiState.close();
            }
            return;
        }
        const wasActive = this.#runtimeState.isActive();
        if (wasActive) {
            this.#turnManager.interruptActiveConversation();
        }
        this.#deactivate();
        await this.#teardown.perform();
        if (wasActive) {
            playSoundEffect('microphoneClose');
        }
        if (reason === 'user') {
            this.#host.feedback.show(i18n.t('chat.voiceCall.ended'), 'info');
        } else if (reason === 'disabled') {
            this.#host.feedback.show(i18n.t('chat.voiceCall.disabled'), 'warning');
        }
        if (reason !== 'modal') {
            this.#uiState.close();
        }
        this.#uiState.setStatus('idle', null);
    };

    handleConversationChanged(conversationId: string | null): void {
        if (!this.#runtimeState.isRuntimeActive()) {
            return;
        }
        const boundConversationId = this.#turnManager.getBoundConversationId();
        const nextConversationId = toTrimmedString(conversationId);
        const conversationChanged = boundConversationId === null ? Boolean(nextConversationId) : boundConversationId !== nextConversationId;
        const initialBindingChange = boundConversationId === null && conversationChanged;
        if (initialBindingChange && this.#turnManager.isInitialBindingPending()) {
            return;
        }
        if (conversationChanged) {
            this.#stopForConversationSwitch();
        }
    }

    handleStreamTerminalized(update: ChatStreamTerminalUpdate): void {
        if (!this.#runtimeState.isActive()) {
            return;
        }
        if (!this.#speaker.markTerminalized(update)) {
            return;
        }
        if (this.#pauseController.isPaused()) {
            return;
        }
        this.#assistantStatus.reconcile();
    }

    #stopForConversationSwitch(): void {
        this.stop('hide').catch((error) => {
            errorHandler.warn('VoiceCallController', 'Voice call conversation switch handling failed', ensureError(error));
        });
    }

    async dispose(): Promise<void> {
        if (this.#runtimeState.isActive()) {
            this.#turnManager.interruptActiveConversation();
        }
        this.#deactivate();
        await this.#teardown.perform();
        this.#uiState.close();
        this.#uiState.dispose();
        this.#speechEventsExit();
        this.#speechEvents.clear();
    }
}

export { VoiceCallController };
