/* SoAI - Chat voice call modal scaffold [frontend/assets/ts/features/chat/modals/voiceCallModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { CHAT_VOICE_CALL_MODAL_ID } from '@features/chat/modals/constants.ts';

const VOICE_CALL_PAUSE_ACTION = 'voice-call:pause';
const VOICE_CALL_END_ACTION = 'voice-call:end';

const renderVoiceCallBody = (): ReturnType<typeof uiHtml> => {
    const microphoneIcon = renderIconSlot(getIconSync('microphone', { size: 34, strokeWidth: 1.5 }), { className: 'voice-call-modal-icon' });
    const pauseIcon = renderIconSlot(getIconSync('pause', { size: 24, strokeWidth: 1.8 }), { className: 'voice-call-control-icon' });
    const endIcon = renderIconSlot(getIconSync('call', { size: 24, strokeWidth: 1.8 }), { className: 'voice-call-control-icon' });
    return uiHtml`<div class="voice-call-modal-body" data-voice-call-status="idle">
        <div class="voice-call-orb-row">
            <button type="button" class="voice-call-control-orb voice-call-pause-orb" data-action="${VOICE_CALL_PAUSE_ACTION}" ${renderLabelAttributes(i18n.t('chat.voiceCallModal.pauseCall'))} aria-pressed="false" disabled>
                ${pauseIcon}
            </button>
            <div class="voice-call-orb">${microphoneIcon}</div>
            <button type="button" class="voice-call-control-orb voice-call-end-orb" data-action="${VOICE_CALL_END_ACTION}" ${renderLabelAttributes(i18n.t('chat.voiceCallModal.endCallAria'))} disabled>
                ${endIcon}
            </button>
        </div>
        <div class="voice-call-status">
            <div class="voice-call-status-heading">
                <div class="voice-call-status-spinner loading-spinner" aria-hidden="true"></div>
                <div class="voice-call-status-title">${i18n.t('chat.voiceCallModal.idleTitle')}</div>
            </div>
            <div class="voice-call-status-detail">${i18n.t('chat.voiceCallModal.idleDetail')}</div>
        </div>
        <div class="voice-call-transcript u-hidden" aria-hidden="true">
            <div class="voice-call-transcript-row voice-call-transcript-user u-hidden" aria-hidden="true">
                <span class="voice-call-transcript-label">${i18n.t('chat.voiceCallModal.userTranscriptLabel')}</span>
                <span class="voice-call-transcript-text"></span>
            </div>
            <div class="voice-call-transcript-row voice-call-transcript-assistant u-hidden" aria-hidden="true">
                <span class="voice-call-transcript-label">${i18n.t('chat.voiceCallModal.assistantTranscriptLabel')}</span>
                <span class="voice-call-transcript-text"></span>
            </div>
        </div>
        <div class="voice-call-error u-hidden" aria-hidden="true"></div>
    </div>`;
};

const createVoiceCallModalDefinition = (): ModalDefinition => ({
    id: CHAT_VOICE_CALL_MODAL_ID,
    layout: 'md',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: () => {
        const modalId = CHAT_VOICE_CALL_MODAL_ID;
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('chat.voiceCallModal.title'),
            description: i18n.t('common.modalDescriptions.voiceCall'),
            closeLabel: i18n.t('common.close')
        });
        const body = renderModalBody(renderVoiceCallBody(), { className: 'voice-call-modal-shell' });
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: i18n.t('common.close') })
        });
        return createModalElement({
            id: modalId,
            rootAttributes: { 'data-page-scope': 'chat' },
            header,
            body,
            footer
        });
    }
});

export { VOICE_CALL_END_ACTION, VOICE_CALL_PAUSE_ACTION, createVoiceCallModalDefinition };
