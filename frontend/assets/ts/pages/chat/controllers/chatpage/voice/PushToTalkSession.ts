/* SoAI - Push-to-talk recording, draft, and durable admission session [frontend/assets/ts/pages/chat/controllers/chatpage/voice/PushToTalkSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { AudioRecordingSnapshot, AudioRecordingTerminalOutcome, AudioRecordingTimerHost, ChatAudioManager, ComposerDraftSurfaceSnapshot } from '@features/chat/public.ts';
import type { ConversationInputComposerOutcome, QueuedSendGuardContext, QueueConversationInputOptions } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';
import type { GeometryPoint } from '@core/layout/elementGeometry.ts';
import { PushToTalkPresentationController } from '@pages/chat/controllers/chatpage/voice/PushToTalkPresentationController.ts';

interface PushToTalkSessionDependencies {
    audio: Pick<ChatAudioManager, 'cancelRecording' | 'startRecording' | 'state' | 'stopRecording'>;
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
    onFinished(session: PushToTalkSession): void;
}

class PushToTalkSession {
    readonly #dependencies: PushToTalkSessionDependencies;
    readonly #presentation: PushToTalkPresentationController;
    readonly #abortController = new AbortController();
    readonly #sessionId: number;
    #latestSnapshot: AudioRecordingSnapshot;
    #released = false;
    #terminal = false;
    #terminalOutcomeHandled = false;
    #submissionStarted = false;
    #preparingAdmission = false;
    #pendingCreatedConversationId: string | null = null;
    #finished = false;
    #cleanupEvents: (() => void) | null;
    #statusTimer: number | null = null;

    constructor(dependencies: PushToTalkSessionDependencies) {
        this.#dependencies = dependencies;
        this.#presentation = new PushToTalkPresentationController(dependencies.button, dependencies.start, dependencies.timers);
        const start = dependencies.audio.startRecording('push-to-talk');
        if (!start) {
            this.#presentation.dispose();
            throw new Error('Push-to-talk requires an idle audio manager');
        }
        this.#sessionId = start.sessionId;
        this.#latestSnapshot = { state: 'requesting', sessionId: start.sessionId, intent: 'push-to-talk', presentation: 'default', elapsedMs: 0, canCancel: true, errorText: null };
        this.#cleanupEvents = this.#bindCancellationEvents();
        terminateHandledPromise(
            start.started.then((started) => {
                if (started && !this.#terminal) this.#presentation.markRecordingStarted();
            })
        );
    }

    get sessionId(): number {
        return this.#sessionId;
    }

    move(current: GeometryPoint): void {
        if (this.#released || this.#terminal) return;
        const cancellationArmed = this.#presentation.move(current);
        if (this.#latestSnapshot.state === 'recording') this.#present(cancellationArmed ? 'ptt-release-to-cancel' : 'ptt-release-to-send');
    }

    release(current: GeometryPoint): void {
        if (this.#released || this.#terminal) return;
        this.move(current);
        this.#released = true;
        this.#presentation.finish();
        if (this.#presentation.cancellationArmed) {
            this.cancel(true);
            return;
        }
        if (this.#dependencies.audio.state === 'requesting') {
            this.cancel(false);
            return;
        }
        if (this.#dependencies.audio.state !== 'recording') return;
        this.#dependencies.audio.stopRecording(this.#sessionId);
        if (!this.#terminal) this.#present('default');
    }

    cancel(showStatus: boolean): void {
        if (this.#terminal || this.#submissionStarted) return;
        this.#terminal = true;
        this.#abortController.abort();
        this.#dependencies.audio.cancelRecording(this.#sessionId);
        this.#presentation.finish();
        if (showStatus) {
            this.#present('ptt-cancelled');
            this.#statusTimer = this.#dependencies.timers.setTimeout(() => this.#finish(), 900);
        } else {
            this.#finish();
        }
    }

    handleAudioSnapshot(snapshot: AudioRecordingSnapshot): boolean {
        if (snapshot.sessionId !== this.#sessionId || this.#terminal) return false;
        this.#latestSnapshot = snapshot;
        if (snapshot.state === 'recording') {
            this.#presentation.markRecordingStarted();
            this.#present(this.#presentation.cancellationArmed ? 'ptt-release-to-cancel' : 'ptt-release-to-send');
        } else {
            this.#dependencies.present(snapshot);
        }
        return true;
    }

    handleTerminal(outcome: AudioRecordingTerminalOutcome): boolean {
        if (outcome.sessionId !== this.#sessionId || outcome.intent !== 'push-to-talk') return false;
        if (this.#terminalOutcomeHandled || this.#terminal) return true;
        this.#terminalOutcomeHandled = true;
        if (outcome.status !== 'transcript') {
            this.#terminal = true;
            this.#finish(outcome.status !== 'failed');
            return true;
        }
        terminateHandledPromise(this.#completeTranscript(outcome.text));
        return true;
    }

    handleConversationChanged(conversationId: string | null): void {
        if (conversationId === this.#dependencies.conversationId) return;
        if (this.#dependencies.conversationId === null && this.#preparingAdmission && conversationId !== null) {
            if (this.#pendingCreatedConversationId === null) this.#pendingCreatedConversationId = conversationId;
            if (this.#pendingCreatedConversationId === conversationId) return;
        }
        this.cancel(false);
    }

    #bindCancellationEvents(): () => void {
        const documentRef = this.#dependencies.button.ownerDocument;
        return bindEventGroup(
            [
                {
                    target: documentRef,
                    type: 'keydown',
                    listener: (event) => {
                        if (event instanceof KeyboardEvent && event.key === 'Escape') this.cancel(false);
                    },
                    options: { capture: true }
                },
                {
                    target: documentRef,
                    type: 'visibilitychange',
                    listener: () => {
                        if (documentRef.hidden) this.cancel(false);
                    }
                },
                {
                    target: this.#dependencies.lifecycleSignal,
                    type: 'abort',
                    listener: () => this.cancel(false)
                }
            ],
            this.#abortController.signal
        );
    }

    async #completeTranscript(text: string): Promise<void> {
        if (!this.#hasOriginalOwnership()) {
            this.#terminal = true;
            this.#finish();
            return;
        }
        const unchanged = this.#dependencies.matchesDraftSurface(this.#dependencies.draftSnapshot) && this.#dependencies.getModelId() === this.#dependencies.modelId;
        this.#dependencies.insertTranscript(text);
        const combinedSnapshot = this.#dependencies.captureDraftSurface();
        if (!unchanged) {
            this.#terminal = true;
            this.#present('ptt-review');
            this.#finishAfterStatus();
            return;
        }
        this.#present('ptt-sending');
        const beforeSend = (context: QueuedSendGuardContext): boolean | { allowed: false; reason: 'stale' } => {
            const createdConversationId = this.#resolveCreatedConversationId(context);
            const surfaceMatches = this.#dependencies.matchesDraftSurface(combinedSnapshot, createdConversationId ?? undefined);
            const ownershipMatches = createdConversationId === null ? this.#hasOriginalOwnership() : surfaceMatches;
            const allowed = !this.#terminal && ownershipMatches && this.#dependencies.getModelId() === this.#dependencies.modelId && surfaceMatches;
            if (!allowed && this.#pendingCreatedConversationId !== null && createdConversationId === null && !this.#submissionStarted) this.cancel(false);
            return allowed ? true : { allowed: false, reason: 'stale' };
        };
        this.#preparingAdmission = true;
        try {
            const outcome = await this.#dependencies.queueInput({
                signal: this.#abortController.signal,
                beforeSend,
                onAdmissionStarted: () => {
                    this.#submissionStarted = true;
                    this.#present('ptt-sending');
                },
                onEffectiveSendCommitted: () => {
                    this.#present('ptt-queued');
                }
            });
            if (this.#finished || (this.#terminal && !this.#submissionStarted)) return;
            this.#terminal = true;
            if (outcome !== 'enqueued') this.#present('ptt-review');
            this.#finishAfterStatus();
        } catch (error) {
            if (this.#finished || this.#terminal) return;
            this.#terminal = true;
            this.#present('ptt-review');
            this.#finishAfterStatus();
            throw error;
        }
    }

    #hasOriginalOwnership(): boolean {
        const current = this.#dependencies.captureDraftSurface();
        return this.#dependencies.getConversationId() === this.#dependencies.conversationId && current.conversationId === this.#dependencies.draftSnapshot.conversationId && current.generation === this.#dependencies.draftSnapshot.generation;
    }

    #resolveCreatedConversationId(context: QueuedSendGuardContext): string | null {
        const pendingConversationId = this.#pendingCreatedConversationId;
        if (this.#dependencies.conversationId !== null || pendingConversationId === null || context.conversationId !== pendingConversationId || !context.startedFromEmptyConversation || !context.createdConversationForSend) return null;
        return pendingConversationId;
    }

    #present(presentation: AudioRecordingSnapshot['presentation']): void {
        const state = presentation === 'ptt-release-to-send' || presentation === 'ptt-release-to-cancel' ? 'recording' : presentation === 'default' ? this.#latestSnapshot.state : 'idle';
        this.#dependencies.present({ ...this.#latestSnapshot, state, presentation, canCancel: !this.#submissionStarted && !this.#terminal, errorText: null });
    }

    #finishAfterStatus(): void {
        this.#statusTimer = this.#dependencies.timers.setTimeout(() => this.#finish(), 1_200);
    }

    #finish(clearPreview = true): void {
        if (this.#finished) return;
        this.#finished = true;
        if (this.#statusTimer !== null) this.#dependencies.timers.clearTimeout(this.#statusTimer);
        this.#statusTimer = null;
        this.#abortController.abort();
        this.#cleanupEvents?.();
        this.#cleanupEvents = null;
        this.#presentation.dispose();
        if (clearPreview) this.#dependencies.present({ state: 'idle', sessionId: null, intent: null, presentation: 'default', elapsedMs: 0, canCancel: false, errorText: null });
        this.#dependencies.onFinished(this);
    }
}

export { PushToTalkSession };
export type { PushToTalkSessionDependencies };
