/* SoAI - Chat feature audio manager [frontend/assets/ts/features/chat/ChatAudioManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveGetUserMediaError } from '@core/media/audioCaptureSupport.ts';
import { stopMediaStreamTracks } from '@core/media/mediaCleanup.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { resolveSupportedRecordingMimeType, transcribeAudioBlob, type WebuiMediaApiClient } from '@features/chat/api/webuiMediaAudio.ts';
import { AudioRecordingSnapshotController } from '@features/chat/audio/AudioRecordingSnapshotController.ts';
import type { ActiveAudioState, AudioRecordingIntent, AudioRecordingSnapshot, AudioRecordingStart, AudioRecordingTerminalOutcome, AudioRecordingTimerHost, AudioState } from '@features/chat/audio/audioRecordingTypes.ts';
import type { ChatAttachmentErrorHandler } from '@features/chat/ChatTypes.ts';

const PUSH_TO_TALK_STARTUP_DEADLINE_MS = 30_000;

interface ChatAudioManagerOptions {
    apiClient: WebuiMediaApiClient | null;
    resolveSttModel: () => string;
    beforeStart?: (() => Promise<void>) | undefined;
    timers: AudioRecordingTimerHost;
    onStateChange: (state: AudioState, intent: AudioRecordingIntent | null) => void;
    onRecordingSnapshotChange: (snapshot: AudioRecordingSnapshot) => void;
    onError: ChatAttachmentErrorHandler;
    onTerminalOutcome: (outcome: AudioRecordingTerminalOutcome) => void;
}

interface ActiveRecordingSession {
    id: number;
    intent: AudioRecordingIntent;
    terminal: boolean;
    processingStarted: boolean;
    startupTimer: number | null;
    cancelStartup: (() => void) | null;
}

class ChatAudioManager {
    readonly #apiClient: WebuiMediaApiClient | null;
    readonly #snapshotController: AudioRecordingSnapshotController;
    readonly #resolveSttModel: () => string;
    readonly #beforeStart: (() => Promise<void>) | null;
    readonly #timers: AudioRecordingTimerHost;
    readonly #onStateChange: (state: AudioState, intent: AudioRecordingIntent | null) => void;
    readonly #onError: ChatAttachmentErrorHandler;
    readonly #onTerminalOutcome: (outcome: AudioRecordingTerminalOutcome) => void;
    #state: AudioState = 'idle';
    #mediaRecorder: MediaRecorder | null = null;
    #audioChunks: Blob[] = [];
    #stream: MediaStream | null = null;
    #sessionSequence = 0;
    #activeSession: ActiveRecordingSession | null = null;
    #transcriptionAbort: AbortController | null = null;

    constructor(options: ChatAudioManagerOptions) {
        this.#apiClient = options.apiClient;
        this.#snapshotController = new AudioRecordingSnapshotController({ onSnapshotChange: options.onRecordingSnapshotChange });
        this.#resolveSttModel = options.resolveSttModel;
        this.#beforeStart = options.beforeStart ?? null;
        this.#timers = options.timers;
        this.#onStateChange = options.onStateChange;
        this.#onError = options.onError;
        this.#onTerminalOutcome = options.onTerminalOutcome;
    }

    get state(): AudioState {
        return this.#state;
    }

    isSessionActive(sessionId: number): boolean {
        return this.#activeSession?.id === sessionId;
    }

    startRecording(intent: AudioRecordingIntent = 'dictation'): AudioRecordingStart | null {
        if (this.#state !== 'idle') return null;
        const session: ActiveRecordingSession = { id: ++this.#sessionSequence, intent, terminal: false, processingStarted: false, startupTimer: null, cancelStartup: null };
        this.#activeSession = session;
        this.#beginState('requesting', session);
        return { sessionId: session.id, started: this.#startSession(session) };
    }

    stopRecording(sessionId?: number): void {
        const session = this.#activeSession;
        if (!session || (sessionId !== undefined && session.id !== sessionId) || this.#state !== 'recording' || !this.#mediaRecorder) return;
        this.#setState('processing', session.intent);
        try {
            this.#mediaRecorder.stop();
        } catch (error) {
            this.#handleError(session, ensureError(error), i18n.t('chat.audio.recordingFailed'));
        }
    }

    cancelRecording(sessionId?: number): void {
        const session = this.#activeSession;
        if (!session || (sessionId !== undefined && session.id !== sessionId)) {
            if (this.#state === 'idle') this.#snapshotController.emit(null);
            return;
        }
        this.#invalidateSession(session);
        this.#abortTranscription();
        let cleanupError: Error | null = null;
        try {
            if (this.#mediaRecorder && this.#mediaRecorder.state !== 'inactive') this.#mediaRecorder.stop();
        } catch (error) {
            cleanupError = ensureError(error);
        }
        this.#finishIdle(session);
        this.#emitTerminal(session, { status: 'cancelled', sessionId: session.id, intent: session.intent });
        if (cleanupError) this.#onError(cleanupError, i18n.t('chat.audio.recordingFailed'), { notify: false });
    }

    toggleRecording(): void {
        if (this.#state === 'idle') {
            const start = this.startRecording('dictation');
            if (start) terminateHandledPromise(start.started);
        } else if (this.#state === 'recording') {
            this.stopRecording();
        }
    }

    async #startSession(session: ActiveRecordingSession): Promise<boolean> {
        if (!isFunction(navigator?.mediaDevices?.getUserMedia)) {
            this.#handleError(session, new Error('MediaDevices API not supported'), i18n.t('chat.audio.notSupported'));
            return false;
        }
        try {
            const acquisition = this.#acquireMediaStream(session);
            const stream = session.intent === 'push-to-talk' ? await Promise.race([acquisition, this.#startupDeadline(session)]) : await acquisition;
            this.#clearStartupTimer(session);
            if (!stream || !this.#isActive(session)) return false;
            this.#stream = stream;
            this.#audioChunks = [];
            const recorder = new MediaRecorder(stream, { mimeType: resolveSupportedRecordingMimeType() });
            this.#mediaRecorder = recorder;
            recorder.ondataavailable = (event: BlobEvent): void => {
                if (this.#isActive(session) && event.data.size > 0) this.#audioChunks.push(event.data);
            };
            recorder.onstop = (): void => {
                if (!this.#isActive(session) || session.processingStarted) return;
                session.processingStarted = true;
                terminateHandledPromise(this.#processRecording(session));
            };
            recorder.onerror = (): void => {
                if (this.#isActive(session)) this.#handleError(session, new Error('Recording failed'), i18n.t('chat.audio.recordingFailed'));
            };
            recorder.start();
            this.#beginState('recording', session);
            return true;
        } catch (error) {
            this.#clearStartupTimer(session);
            if (!this.#isActive(session)) return false;
            const runtimeError = ensureError(error);
            const title = runtimeError.message === 'Push-to-talk microphone startup deadline exceeded' ? i18n.t('chat.audio.initFailed') : resolveGetUserMediaError(runtimeError);
            this.#handleError(session, runtimeError, title);
        }
        return false;
    }

    async #acquireMediaStream(session: ActiveRecordingSession): Promise<MediaStream | null> {
        await this.#beforeStart?.();
        if (!this.#isActive(session)) return null;
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (!this.#isActive(session)) {
            stopMediaStreamTracks(stream);
            return null;
        }
        return stream;
    }

    #startupDeadline(session: ActiveRecordingSession): Promise<never> {
        const deadline = createDeferred<never>();
        session.startupTimer = this.#timers.setTimeout(() => deadline.reject(new Error('Push-to-talk microphone startup deadline exceeded')), PUSH_TO_TALK_STARTUP_DEADLINE_MS);
        session.cancelStartup = () => deadline.reject(new Error('Push-to-talk microphone startup cancelled'));
        return deadline.promise;
    }

    async #processRecording(session: ActiveRecordingSession): Promise<void> {
        if (!this.#isActive(session)) return;
        this.#stopMediaStream();
        const recorder = this.#mediaRecorder;
        if (this.#audioChunks.length === 0) {
            this.#completeEmpty(session);
            return;
        }
        if (!recorder || !isString(recorder.mimeType) || !recorder.mimeType) {
            this.#handleError(session, new Error('Missing recorder mime type'), i18n.t('chat.audio.recordingFailed'));
            return;
        }
        const mimeType = recorder.mimeType;
        const audioBlob = new Blob(this.#audioChunks, { type: mimeType });
        this.#audioChunks = [];
        if (audioBlob.size === 0) {
            this.#completeEmpty(session);
            return;
        }
        try {
            const abortController = new AbortController();
            this.#transcriptionAbort = abortController;
            const transcription = await transcribeAudioBlob({ apiClient: this.#apiClient, blob: audioBlob, mimeType, filenameStem: 'recording', model: this.#resolveSttModel(), signal: abortController.signal, context: 'ChatAudioManager' });
            if (!this.#isActive(session)) return;
            const text = isString(transcription) ? transcription.trim() : '';
            this.#transcriptionAbort = null;
            this.#invalidateSession(session);
            this.#finishIdle(session);
            this.#emitTerminal(session, text ? { status: 'transcript', sessionId: session.id, intent: session.intent, text } : { status: 'empty', sessionId: session.id, intent: session.intent });
        } catch (error) {
            if (this.#isActive(session)) this.#handleError(session, ensureError(error), i18n.t('chat.audio.transcriptionFailed'));
        } finally {
            if (this.#activeSession === session) this.#transcriptionAbort = null;
        }
    }

    #completeEmpty(session: ActiveRecordingSession): void {
        this.#invalidateSession(session);
        this.#finishIdle(session);
        this.#emitTerminal(session, { status: 'empty', sessionId: session.id, intent: session.intent });
    }

    #handleError(session: ActiveRecordingSession, error: Error, title: string): void {
        if (!this.#isActive(session)) return;
        this.#invalidateSession(session);
        this.#abortTranscription();
        this.#state = 'idle';
        this.#onStateChange('idle', session.intent);
        this.#cleanup();
        this.#snapshotController.fail(title);
        this.#emitTerminal(session, { status: 'failed', sessionId: session.id, intent: session.intent, error });
        this.#onError(error, title, { notify: false });
    }

    #beginState(state: ActiveAudioState, session: ActiveRecordingSession): void {
        this.#state = state;
        this.#onStateChange(state, session.intent);
        this.#snapshotController.begin(state, session.id, session.intent);
    }

    #setState(state: AudioState, intent: AudioRecordingIntent | null): void {
        if (this.#state === state) return;
        this.#state = state;
        this.#onStateChange(state, intent);
        this.#snapshotController.setState(state);
    }

    #isActive(session: ActiveRecordingSession): boolean {
        return this.#activeSession === session && session.id === this.#sessionSequence;
    }

    #invalidateSession(session: ActiveRecordingSession): void {
        if (this.#activeSession !== session) return;
        const cancelStartup = session.cancelStartup;
        this.#clearStartupTimer(session);
        this.#activeSession = null;
        this.#sessionSequence += 1;
        cancelStartup?.();
    }

    #emitTerminal(session: ActiveRecordingSession, outcome: AudioRecordingTerminalOutcome): void {
        if (session.terminal) return;
        session.terminal = true;
        this.#onTerminalOutcome(outcome);
    }

    #clearStartupTimer(session: ActiveRecordingSession): void {
        if (session.startupTimer === null) return;
        this.#timers.clearTimeout(session.startupTimer);
        session.startupTimer = null;
        session.cancelStartup = null;
    }

    #finishIdle(session: ActiveRecordingSession): void {
        this.#setState('idle', session.intent);
        this.#cleanup();
    }

    #stopMediaStream(): void {
        stopMediaStreamTracks(this.#stream);
        this.#stream = null;
    }

    #cleanup(): void {
        this.#stopMediaStream();
        if (this.#mediaRecorder) {
            this.#mediaRecorder.ondataavailable = null;
            this.#mediaRecorder.onstop = null;
            this.#mediaRecorder.onerror = null;
        }
        this.#mediaRecorder = null;
        this.#audioChunks = [];
    }

    #abortTranscription(): void {
        this.#transcriptionAbort?.abort();
        this.#transcriptionAbort = null;
    }

    dispose(): void {
        const session = this.#activeSession;
        if (session) this.cancelRecording(session.id);
        this.#abortTranscription();
        this.#cleanup();
        this.#state = 'idle';
        this.#snapshotController.dispose();
    }
}

export { ChatAudioManager, PUSH_TO_TALK_STARTUP_DEADLINE_MS };
export type { AudioRecordingIntent, AudioRecordingSnapshot, AudioRecordingStart, AudioRecordingTerminalOutcome, AudioRecordingTimerHost, AudioState, ChatAudioManagerOptions };
