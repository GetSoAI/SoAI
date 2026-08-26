/* SoAI - Chat feature audio manager [frontend/assets/ts/features/chat/ChatAudioManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { stopMediaStreamTracks } from '@core/media/mediaCleanup.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { resolveSupportedRecordingMimeType, transcribeAudioBlob, type WebuiMediaApiClient } from '@features/chat/api/webuiMediaAudio.ts';
import { AudioRecordingSnapshotController } from '@features/chat/audio/AudioRecordingSnapshotController.ts';
import type { ActiveAudioState, AudioRecordingSnapshot, AudioState } from '@features/chat/audio/audioRecordingTypes.ts';
import type { ChatAttachmentErrorHandler } from '@features/chat/ChatTypes.ts';

interface ChatAudioManagerOptions {
    apiClient: WebuiMediaApiClient | null;
    resolveSttModel: () => string;
    beforeStart?: (() => Promise<void>) | undefined;
    onStateChange: (state: AudioState) => void;
    onRecordingSnapshotChange: (snapshot: AudioRecordingSnapshot) => void;
    onError: ChatAttachmentErrorHandler;
    onTranscription: (text: string) => void;
}

class ChatAudioManager {
    readonly #apiClient: WebuiMediaApiClient | null;
    #state: AudioState;
    #mediaRecorder: MediaRecorder | null;
    #audioChunks: Blob[];
    #stream: MediaStream | null;
    #recordingSessionId: number;
    #transcriptionAbort: AbortController | null = null;
    #snapshotController: AudioRecordingSnapshotController;
    #resolveSttModel: () => string;
    #beforeStart: (() => Promise<void>) | null;
    #onStateChange: (state: AudioState) => void;
    #onError: ChatAttachmentErrorHandler;
    #onTranscription: (text: string) => void;

    constructor(options: ChatAudioManagerOptions) {
        this.#apiClient = options.apiClient;
        this.#state = 'idle';
        this.#mediaRecorder = null;
        this.#audioChunks = [];
        this.#stream = null;
        this.#recordingSessionId = 0;
        this.#snapshotController = new AudioRecordingSnapshotController({
            onSnapshotChange: options.onRecordingSnapshotChange
        });
        this.#resolveSttModel = options.resolveSttModel;
        this.#beforeStart = options.beforeStart ?? null;
        this.#onStateChange = options.onStateChange;
        this.#onError = options.onError;
        this.#onTranscription = options.onTranscription;
    }

    #setState(newState: AudioState): void {
        if (this.#state === newState) return;
        this.#state = newState;
        this.#onStateChange(newState);
        this.#snapshotController.setState(newState);
    }

    #beginState(newState: ActiveAudioState): void {
        if (this.#state === newState) return;
        this.#state = newState;
        this.#onStateChange(newState);
        this.#snapshotController.begin(newState);
    }

    #handleError(error: Error, title: string): void {
        this.#recordingSessionId += 1;
        this.#abortTranscription();
        this.#state = 'idle';
        this.#onStateChange('idle');
        this.#cleanup();
        this.#snapshotController.fail(title);
        this.#onError(error, title, { notify: true });
    }

    #finishIdle(): void {
        this.#setState('idle');
        this.#cleanup();
    }

    #isActiveSession(recordingSessionId: number): boolean {
        return this.#recordingSessionId === recordingSessionId;
    }

    async startRecording(): Promise<void> {
        if (this.#state !== 'idle') return;
        const recordingSessionId = this.#recordingSessionId + 1;
        this.#recordingSessionId = recordingSessionId;
        this.#beginState('requesting');

        if (!isFunction(navigator?.mediaDevices?.getUserMedia)) {
            this.#handleError(new Error('MediaDevices API not supported'), i18n.t('chat.audio.notSupported'));
            return;
        }

        try {
            if (this.#beforeStart) {
                await this.#beforeStart();
            }
            if (!this.#isActiveSession(recordingSessionId)) {
                return;
            }
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            if (!this.#isActiveSession(recordingSessionId)) {
                stopMediaStreamTracks(stream);
                return;
            }
            this.#stream = stream;
            this.#audioChunks = [];

            const mimeType = resolveSupportedRecordingMimeType();
            this.#mediaRecorder = new MediaRecorder(this.#stream, { mimeType });

            this.#mediaRecorder.ondataavailable = (event: BlobEvent): void => {
                if (!this.#isActiveSession(recordingSessionId)) {
                    return;
                }
                if (event.data.size > 0) {
                    this.#audioChunks.push(event.data);
                }
            };

            this.#mediaRecorder.onstop = (): void => {
                if (!this.#isActiveSession(recordingSessionId)) {
                    return;
                }
                terminateHandledPromise(this.#processRecording(recordingSessionId));
            };

            this.#mediaRecorder.onerror = (): void => {
                if (!this.#isActiveSession(recordingSessionId)) {
                    return;
                }
                this.#handleError(new Error('Recording failed'), i18n.t('chat.audio.recordingFailed'));
            };

            this.#mediaRecorder.start();
            this.#setState('recording');
        } catch (error) {
            if (!this.#isActiveSession(recordingSessionId)) {
                return;
            }
            const err = ensureError(error);
            const isPermissionDenied = err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError';
            if (isPermissionDenied) {
                this.#handleError(err, i18n.t('chat.audio.permissionDenied'));
            } else {
                this.#handleError(err, i18n.t('chat.audio.initFailed'));
            }
        }
    }

    stopRecording(): void {
        if (this.#state !== 'recording' || !this.#mediaRecorder) return;
        this.#mediaRecorder.stop();
        this.#setState('processing');
    }

    cancelRecording(): void {
        if (this.#state === 'idle') {
            this.#snapshotController.emit(null);
            return;
        }
        this.#recordingSessionId += 1;
        this.#abortTranscription();
        if (this.#mediaRecorder && this.#mediaRecorder.state !== 'inactive') {
            this.#mediaRecorder.stop();
        }
        this.#finishIdle();
    }

    toggleRecording(): void {
        if (this.#state === 'idle') {
            terminateHandledPromise(this.startRecording());
        } else if (this.#state === 'recording') {
            this.stopRecording();
        }
    }

    async #processRecording(recordingSessionId: number): Promise<void> {
        if (!this.#isActiveSession(recordingSessionId)) {
            return;
        }
        this.#stopMediaStream();

        if (this.#audioChunks.length === 0) {
            this.#finishIdle();
            return;
        }

        const recorder = this.#mediaRecorder;
        if (!recorder || !isString(recorder.mimeType) || !recorder.mimeType) {
            this.#handleError(new Error('Missing recorder mime type'), i18n.t('chat.audio.recordingFailed'));
            return;
        }
        const mimeType = recorder.mimeType;
        const audioBlob = new Blob(this.#audioChunks, { type: mimeType });
        this.#audioChunks = [];

        if (audioBlob.size === 0) {
            this.#finishIdle();
            return;
        }

        try {
            const abortController = new AbortController();
            this.#transcriptionAbort = abortController;
            const transcription = await this.#sendForTranscription(audioBlob, mimeType, abortController.signal);
            if (!this.#isActiveSession(recordingSessionId)) {
                return;
            }

            if (isString(transcription) && transcription.trim().length > 0) {
                this.#onTranscription(transcription.trim());
            }
            this.#finishIdle();
        } catch (error) {
            if (!this.#isActiveSession(recordingSessionId)) {
                return;
            }
            const err = ensureError(error);
            this.#handleError(err, i18n.t('chat.audio.transcriptionFailed'));
        } finally {
            if (this.#isActiveSession(recordingSessionId)) {
                this.#transcriptionAbort = null;
            }
        }
    }

    async #sendForTranscription(audioBlob: Blob, mimeType: string, signal: AbortSignal): Promise<string> {
        return await transcribeAudioBlob({
            apiClient: this.#apiClient,
            blob: audioBlob,
            mimeType,
            filenameStem: 'recording',
            model: this.#resolveSttModel(),
            signal,
            context: 'ChatAudioManager'
        });
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
        this.#recordingSessionId += 1;
        this.#abortTranscription();
        if (this.#state === 'recording' && this.#mediaRecorder) {
            this.#mediaRecorder.stop();
        }
        this.#cleanup();
        this.#state = 'idle';
        this.#snapshotController.dispose();
    }
}

export { ChatAudioManager };
export type { AudioState, AudioRecordingSnapshot, ChatAudioManagerOptions };
