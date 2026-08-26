/* SoAI - Chat voice call modal UI controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallModalUiController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { dom } from '@core/dom/dom.ts';
import { requireRootButton, requireRootHTMLElement } from '@core/dom/typedElementResolver.ts';
import { requireModalPresenter, type ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { setIconSlot } from '@core/ui/icons/view.ts';
import { CHAT_VOICE_CALL_MODAL_ID, VOICE_CALL_END_ACTION, VOICE_CALL_PAUSE_ACTION } from '@features/chat/public.ts';
import type { VoiceCallTranscriptSnapshot, VoiceCallUiSnapshot, VoiceCallUiStatus } from '@pages/chat/controllers/voicecall/voiceCallTypes.ts';

type VoiceCallModalAction = typeof VOICE_CALL_END_ACTION | typeof VOICE_CALL_PAUSE_ACTION;

interface VoiceCallModalUiControllerHost {
    onEndRequested(): void;
    onPauseRequested(): void;
    onModalClosed(): void;
}

const isVoiceCallModalAction = (value: string | undefined): value is VoiceCallModalAction => value === VOICE_CALL_END_ACTION || value === VOICE_CALL_PAUSE_ACTION;

const resolveStatusTitle = (status: VoiceCallUiStatus): string => {
    if (status === 'idle') return i18n.t('chat.voiceCallModal.idleTitle');
    if (status === 'connecting') return i18n.t('chat.voiceCallModal.connectingTitle');
    if (status === 'speaking') return i18n.t('chat.voiceCallModal.speakingTitle');
    if (status === 'transcribing') return i18n.t('chat.voiceCallModal.transcribingTitle');
    if (status === 'assistantThinking') return i18n.t('chat.voiceCallModal.assistantThinkingTitle');
    if (status === 'assistantSpeaking') return i18n.t('chat.voiceCallModal.assistantSpeakingTitle');
    if (status === 'paused') return i18n.t('chat.voiceCallModal.pausedTitle');
    if (status === 'error') return i18n.t('chat.voiceCallModal.errorTitle');
    return i18n.t('chat.voiceCallModal.listeningTitle');
};

const resolveStatusDetail = (status: VoiceCallUiStatus): string => {
    if (status === 'idle') return i18n.t('chat.voiceCallModal.idleDetail');
    if (status === 'connecting') return i18n.t('chat.voiceCallModal.connectingDetail');
    if (status === 'speaking') return i18n.t('chat.voiceCallModal.speakingDetail');
    if (status === 'transcribing') return i18n.t('chat.voiceCallModal.transcribingDetail');
    if (status === 'assistantThinking') return i18n.t('chat.voiceCallModal.assistantThinkingDetail');
    if (status === 'assistantSpeaking') return i18n.t('chat.voiceCallModal.assistantSpeakingDetail');
    if (status === 'paused') return i18n.t('chat.voiceCallModal.pausedDetail');
    if (status === 'error') return i18n.t('chat.voiceCallModal.errorDetail');
    return i18n.t('chat.voiceCallModal.listeningDetail');
};

const resolveStatusIcon = (status: VoiceCallUiStatus): IconName => {
    if (status === 'assistantSpeaking') return 'speaker';
    if (status === 'assistantThinking') return 'thinking';
    if (status === 'error') return 'warning';
    if (status === 'paused') return 'pause';
    if (status === 'idle' || status === 'connecting') return 'call';
    return 'microphone';
};

const resolvePauseActionLabel = (paused: boolean): string => {
    return paused ? i18n.t('chat.voiceCallModal.resumeCall') : i18n.t('chat.voiceCallModal.pauseCall');
};

class VoiceCallModalUiController {
    #host: VoiceCallModalUiControllerHost;
    #presenter: ModalPresenterApi;
    #abortController: AbortController | null = null;
    #programmaticClose = false;

    constructor(host: VoiceCallModalUiControllerHost) {
        this.#host = host;
        this.#presenter = requireModalPresenter();
    }

    open(): void {
        const modal = this.#presenter.requireElement(CHAT_VOICE_CALL_MODAL_ID);
        this.#bind(modal);
        this.#presenter.open(CHAT_VOICE_CALL_MODAL_ID);
    }

    close(): void {
        if (!this.#presenter.isOpen(CHAT_VOICE_CALL_MODAL_ID)) {
            return;
        }
        this.#programmaticClose = true;
        try {
            this.#presenter.close(CHAT_VOICE_CALL_MODAL_ID, { reason: 'voice-call-ended' });
        } finally {
            this.#programmaticClose = false;
        }
    }

    update(snapshot: VoiceCallUiSnapshot): void {
        const modal = this.#presenter.requireElement(CHAT_VOICE_CALL_MODAL_ID);
        const body = requireRootHTMLElement(modal, '.voice-call-modal-body', 'voice call modal body');
        body.setAttribute('data-voice-call-status', snapshot.status);
        const level = Math.round(Math.max(0, Math.min(1, snapshot.level)) * 100);
        dom.setStyle(body, '--voice-call-level', String(level));
        setIconSlot(requireRootHTMLElement(modal, '.voice-call-modal-icon', 'voice call modal icon'), getIconSync(resolveStatusIcon(snapshot.status), { size: 34, strokeWidth: 1.5 }), { className: 'voice-call-modal-icon' });
        dom.setText(requireRootHTMLElement(modal, '.voice-call-status-title', 'voice call status title'), resolveStatusTitle(snapshot.status));
        dom.setText(requireRootHTMLElement(modal, '.voice-call-status-detail', 'voice call status detail'), resolveStatusDetail(snapshot.status));
        this.#syncTranscript(modal, snapshot.transcript);
        this.#syncOptionalText(modal, '.voice-call-error', snapshot.errorText);
        this.#syncControlButtons(modal, snapshot);
    }

    dispose(): void {
        this.#abortController?.abort();
        this.#abortController = null;
    }

    #bind(modal: HTMLElement): void {
        if (this.#abortController) {
            return;
        }
        this.#abortController = new AbortController();
        const signal = this.#abortController.signal;
        bindDataActionListener({
            root: modal,
            eventType: 'click',
            signal,
            isAction: isVoiceCallModalAction,
            preventDefault: 'always',
            mouseButton: 'primary',
            ignoreDisabled: true,
            onAction: ({ action }) => {
                if (action === VOICE_CALL_PAUSE_ACTION) {
                    this.#host.onPauseRequested();
                    return;
                }
                this.#host.onEndRequested();
            }
        });
        modal.addEventListener(
            'core.modal.close',
            () => {
                if (this.#programmaticClose) {
                    return;
                }
                this.#host.onModalClosed();
            },
            { signal }
        );
    }

    #syncOptionalText(modal: HTMLElement, selector: string, text: string | null): void {
        const element = requireRootHTMLElement(modal, selector, 'voice call optional text');
        const normalized = isString(text) ? text.trim() : '';
        dom.setText(element, normalized);
        const hidden = !normalized;
        element.classList.toggle('u-hidden', hidden);
        element.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    }

    #syncTranscript(modal: HTMLElement, transcript: VoiceCallTranscriptSnapshot): void {
        const transcriptElement = requireRootHTMLElement(modal, '.voice-call-transcript', 'voice call transcript');
        const userVisible = this.#syncTranscriptRow(transcriptElement, '.voice-call-transcript-user', transcript.userText);
        const assistantVisible = this.#syncTranscriptRow(transcriptElement, '.voice-call-transcript-assistant', transcript.assistantText);
        this.#syncAssistantCaptionAnimation(transcriptElement, transcript.assistantSequence, assistantVisible);
        const hidden = !userVisible && !assistantVisible;
        transcriptElement.classList.toggle('u-hidden', hidden);
        transcriptElement.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    }

    #syncTranscriptRow(root: HTMLElement, selector: string, text: string | null): boolean {
        const row = requireRootHTMLElement(root, selector, 'voice call transcript row');
        const textElement = requireRootHTMLElement(row, '.voice-call-transcript-text', 'voice call transcript text');
        const normalized = isString(text) ? text.trim() : '';
        dom.setText(textElement, normalized);
        const hidden = !normalized;
        row.classList.toggle('u-hidden', hidden);
        row.setAttribute('aria-hidden', hidden ? 'true' : 'false');
        return !hidden;
    }

    #syncAssistantCaptionAnimation(root: HTMLElement, sequence: number, visible: boolean): void {
        const row = requireRootHTMLElement(root, '.voice-call-transcript-assistant', 'voice call assistant transcript row');
        const currentSequence = row.getAttribute('data-caption-sequence');
        const nextSequence = String(sequence);
        if (!visible || currentSequence === nextSequence) {
            return;
        }
        row.setAttribute('data-caption-sequence', nextSequence);
        row.classList.remove('is-caption-entering');
        const bounds = measureLayoutBox(row);
        if (!Number.isFinite(bounds.width)) {
            return;
        }
        row.classList.add('is-caption-entering');
    }

    #syncControlButtons(modal: HTMLElement, snapshot: VoiceCallUiSnapshot): void {
        const pauseButton = requireRootButton(modal, '.voice-call-pause-orb', 'voice call pause button');
        const pauseLabel = resolvePauseActionLabel(snapshot.paused);
        pauseButton.disabled = !snapshot.active || snapshot.status === 'connecting' || snapshot.status === 'error';
        pauseButton.setAttribute('aria-label', pauseLabel);
        pauseButton.setAttribute('aria-pressed', snapshot.paused ? 'true' : 'false');
        setTooltipText(pauseButton, pauseLabel);
        setIconSlot(requireRootHTMLElement(pauseButton, '.voice-call-control-icon', 'voice call pause icon'), getIconSync(snapshot.paused ? 'play' : 'pause', { size: 24, strokeWidth: snapshot.paused ? 1.5 : 1.8 }), { className: 'voice-call-control-icon' });

        const endButton = requireRootButton(modal, '.voice-call-end-orb', 'voice call end button');
        const endLabel = i18n.t('chat.voiceCallModal.endCallAria');
        endButton.disabled = !snapshot.active;
        endButton.setAttribute('aria-label', endLabel);
        setTooltipText(endButton, endLabel);
    }
}

export { VoiceCallModalUiController };
