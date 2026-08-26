/* SoAI - Chat page input action support controller [frontend/assets/ts/pages/chat/controllers/page/dom/inputActionSupportController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { ChatPageDomHost } from '@pages/chat/controllers/page/dom/contracts.ts';
import type { VisionSupportHost } from '@pages/chat/controllers/page/guards/modelVisionSupportController.ts';

const resolveIsSecureContext = (): boolean => {
    const windowRef = getWindow();
    return windowRef?.isSecureContext === true;
};

const resolveGetUserMediaSupport = (): boolean => {
    const getUserMedia = navigator?.mediaDevices?.getUserMedia;
    return typeof getUserMedia === 'function';
};

const resolveMediaRecorderSupport = (): boolean => {
    return typeof MediaRecorder === 'function';
};

const buildDisabledTooltipText = (actionLabel: string, reason: string): string => {
    return i18n.t('chat.inputActions.disabledWithReason', { action: actionLabel, reason });
};

const applyDisabledStateToActionButton = (button: HTMLButtonElement, baseLabel: string, disabledReason: string | null): void => {
    const disabled = disabledReason !== null;
    button.setAttribute('aria-disabled', disabled ? 'true' : 'false');
    button.setAttribute('data-toggle-disabled', disabled ? 'true' : 'false');
    if (disabled) {
        button.setAttribute('tabindex', '-1');
    } else {
        button.removeAttribute('tabindex');
    }

    const tooltipText = disabledReason ? buildDisabledTooltipText(baseLabel, disabledReason) : baseLabel;
    setTooltipText(button, tooltipText);
    button.setAttribute('aria-label', tooltipText);
};

const resolveCallBaseLabel = (button: HTMLButtonElement): string => {
    const pressed = button.getAttribute('aria-pressed') === 'true' || button.classList.contains('is-active');
    return pressed ? i18n.t('chat.input.voiceCallEnd') : i18n.t('chat.input.voiceCallStart');
};

const resolveMicrophoneBaseLabel = (button: HTMLButtonElement): string => {
    if (button.classList.contains('is-stop-mode')) {
        return button.dataset['stopLabel'] ?? i18n.t('chat.input.stopRecording');
    }
    if (button.classList.contains('is-processing')) {
        return i18n.t('chat.input.transcribing');
    }
    return button.dataset['startLabel'] ?? i18n.t('chat.input.startRecording');
};

const resolveMicrophoneDisabledReason = (): string | null => {
    if (!resolveIsSecureContext()) {
        return i18n.t('chat.inputActions.disabled.requiresHttps');
    }
    if (!resolveGetUserMediaSupport()) {
        return i18n.t('chat.inputActions.disabled.mediaNotSupported');
    }
    if (!resolveMediaRecorderSupport()) {
        return i18n.t('chat.inputActions.disabled.recordingNotSupported');
    }
    return null;
};

const resolveCallDisabledReason = (host: VisionSupportHost): string | null => {
    if (!resolveIsSecureContext()) {
        return i18n.t('chat.inputActions.disabled.requiresHttps');
    }
    if (!resolveGetUserMediaSupport()) {
        return i18n.t('chat.inputActions.disabled.mediaNotSupported');
    }
    const currentModel = host.conversationState.currentModel;
    const normalizedModel = typeof currentModel === 'string' ? currentModel.trim() : '';
    if (!normalizedModel) {
        return i18n.t('chat.voiceCall.noModelSelected');
    }
    return null;
};

const syncActionButtons = (buttons: Element[], resolveBaseLabel: (button: HTMLButtonElement) => string, disabledReason: string | null): void => {
    for (const candidate of buttons) {
        if (!(candidate instanceof HTMLButtonElement)) {
            continue;
        }
        applyDisabledStateToActionButton(candidate, resolveBaseLabel(candidate), disabledReason);
    }
};

const syncChatInputActionSupport = (host: ChatPageDomHost & VisionSupportHost): void => {
    syncActionButtons(host.pageDom.query('.microphone-btn'), resolveMicrophoneBaseLabel, resolveMicrophoneDisabledReason());
    syncActionButtons(host.pageDom.query('.call-btn'), resolveCallBaseLabel, resolveCallDisabledReason(host));
};

export { syncChatInputActionSupport };
