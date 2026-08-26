/* SoAI - Chat page audio [frontend/assets/ts/pages/chat/controllers/page/dom/audio.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { playSoundEffect } from '@core/ui/sound/engine.ts';
import type { AudioState } from '@features/chat/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type MicrophoneButtonHost = PageDomOwnerHost;

interface MicrophoneButtonStateOptions {
    previousState: AudioState;
    soundEffectsEnabled: boolean;
}

const playMicrophoneTransitionSound = (previousState: AudioState, state: AudioState, soundEffectsEnabled: boolean): void => {
    if (!soundEffectsEnabled) {
        return;
    }
    if (state === 'requesting' && previousState === 'idle') {
        playSoundEffect('microphoneOpen');
        return;
    }
    if (previousState === 'recording' && (state === 'processing' || state === 'idle')) {
        playSoundEffect('microphoneClose');
    }
};

const resolveMicrophoneButtonLabel = (button: HTMLButtonElement, state: AudioState): string => {
    if (state === 'recording') {
        return button.dataset['stopLabel'] ?? i18n.t('chat.input.stopRecording');
    }
    if (state === 'processing') {
        return i18n.t('chat.input.transcribing');
    }
    if (state === 'requesting') {
        return i18n.t('chat.input.requestingMicrophone');
    }
    return button.dataset['startLabel'] ?? i18n.t('chat.input.startRecording');
};

const syncMicrophoneButtonState = (host: MicrophoneButtonHost, button: HTMLButtonElement, state: AudioState): void => {
    const label = resolveMicrophoneButtonLabel(button, state);
    button.classList.toggle('is-recording', state === 'recording');
    button.classList.toggle('is-stop-mode', state === 'recording');
    button.classList.toggle('is-processing', state === 'processing' || state === 'requesting');
    setTooltipText(button, label);
    button.setAttribute('aria-label', label);
    const labelElement = host.pageDom.optionalHTMLElement('.chat-input-action-label', button);
    if (labelElement !== null) {
        labelElement.textContent = label;
    }
};

const updateMicrophoneButtonState = (host: MicrophoneButtonHost, state: AudioState, options: MicrophoneButtonStateOptions): void => {
    playMicrophoneTransitionSound(options.previousState, state, options.soundEffectsEnabled);
    for (const candidate of host.pageDom.query('.microphone-btn')) {
        if (candidate instanceof HTMLButtonElement) {
            syncMicrophoneButtonState(host, candidate, state);
        }
    }
};

export { updateMicrophoneButtonState };
