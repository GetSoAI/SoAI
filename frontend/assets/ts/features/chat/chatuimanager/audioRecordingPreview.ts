/* SoAI - Chat microphone recording preview rendering [frontend/assets/ts/features/chat/chatuimanager/audioRecordingPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { syncAttributeValue, syncTextContent } from '@core/dom/patching.ts';
import { optionalRootHTMLElement, requireRootHTMLElement } from '@core/dom/typedElementResolver.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { CHAT_ICON_SIZE_SM } from '@features/chat/chatConstants.ts';
import type { AudioRecordingSnapshot } from '@features/chat/ChatAudioManager.ts';
import { getElement, setElementVisibility } from '@features/chat/chatuimanager/dom.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const PREVIEW_ITEM_SELECTOR = '.voice-recording-preview-item';
const PREVIEW_TITLE_SELECTOR = '.voice-recording-preview-title';
const PREVIEW_STATUS_SELECTOR = '.voice-recording-preview-status-text';
const PREVIEW_SPINNER_SELECTOR = '.voice-recording-preview-spinner';
const PREVIEW_CANCEL_SELECTOR = '.voice-recording-preview-cancel';

const formatElapsedSeconds = (elapsedMs: number): string => {
    const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

const resolveRecordingTitle = (snapshot: AudioRecordingSnapshot): string => {
    if (snapshot.errorText) {
        return i18n.t('chat.audioPreview.errorTitle');
    }
    if (snapshot.state === 'processing') {
        return i18n.t('chat.audioPreview.processingTitle');
    }
    if (snapshot.state === 'requesting') {
        return i18n.t('chat.audioPreview.requestingTitle');
    }
    return i18n.t('chat.audioPreview.recordingTitle');
};

const resolveRecordingStatus = (snapshot: AudioRecordingSnapshot): string => {
    if (snapshot.errorText) {
        return snapshot.errorText;
    }
    if (snapshot.state === 'processing') {
        return i18n.t('chat.audioPreview.processingStatus');
    }
    if (snapshot.state === 'requesting') {
        return i18n.t('chat.audioPreview.requestingStatus');
    }
    return i18n.t('chat.audioPreview.recordingStatus', { elapsed: formatElapsedSeconds(snapshot.elapsedMs) });
};

const renderAudioRecordingPreviewShell = (context: ChatUIManagerContext): TrustedHtml => {
    const icon = context.dependencies.getCachedIcon('microphone', CHAT_ICON_SIZE_SM);
    const actionIcon = context.dependencies.getCachedIcon('close', { size: 12, strokeWidth: 2.2 });
    const actionLabel = i18n.t('chat.audioPreview.cancel');
    return uiHtml`<div class="file-preview-item document voice-recording-preview-item glass-surface-light glass-surface--bordered glass-surface--rounded">
        <span class="file-preview-leading-icon voice-recording-preview-icon" aria-hidden="true">${icon}</span>
        <div class="file-info voice-recording-preview-copy">
            <span class="file-name voice-recording-preview-title"></span>
            <span class="file-status voice-recording-preview-status"><span class="loading-spinner voice-recording-preview-spinner u-hidden" aria-hidden="true"></span><span class="voice-recording-preview-status-text"></span></span>
        </div>
        <button type="button" class="remove-file-btn voice-recording-preview-cancel" data-action="${uiAttr(CHAT_ACTIONS.CANCEL_RECORDING)}" aria-label="${uiAttr(actionLabel)}" data-tooltip="${uiAttr(actionLabel)}">${actionIcon}</button>
    </div>`;
};

const ensureAudioRecordingPreviewShell = (context: ChatUIManagerContext, preview: HTMLElement): void => {
    if (optionalRootHTMLElement(preview, PREVIEW_ITEM_SELECTOR, 'voice recording preview item')) {
        return;
    }
    context.dependencies.updateHTML(preview, renderAudioRecordingPreviewShell(context));
};

const updateAudioRecordingPreview = (context: ChatUIManagerContext, snapshot: AudioRecordingSnapshot): void => {
    const preview = getElement(context, 'voiceRecordingPreview');
    if (!preview) {
        return;
    }
    if (snapshot.state === 'idle' && !snapshot.errorText) {
        context.dependencies.updateHTML(preview, '');
        setElementVisibility(context, 'voiceRecordingPreview', false);
        return;
    }
    const actionLabel = snapshot.errorText ? i18n.t('common.close') : i18n.t('chat.audioPreview.cancel');
    const actionLabelAttr = context.dependencies.sanitizer.attribute(actionLabel);
    ensureAudioRecordingPreviewShell(context, preview);
    syncTextContent(requireRootHTMLElement(preview, PREVIEW_TITLE_SELECTOR, 'voice recording preview title'), resolveRecordingTitle(snapshot));
    syncTextContent(requireRootHTMLElement(preview, PREVIEW_STATUS_SELECTOR, 'voice recording preview status'), resolveRecordingStatus(snapshot));
    const spinner = requireRootHTMLElement(preview, PREVIEW_SPINNER_SELECTOR, 'voice recording preview spinner');
    const spinnerVisible = snapshot.state === 'processing' || snapshot.state === 'requesting';
    const shouldHideSpinner = !spinnerVisible;
    if (spinner.classList.contains(CSS_CLASSES.HIDDEN) !== shouldHideSpinner) {
        context.dependencies.toggleClassName(spinner, CSS_CLASSES.HIDDEN, shouldHideSpinner);
    }
    syncAttributeValue(spinner, 'aria-hidden', spinnerVisible ? 'false' : 'true');
    const cancelButton = requireRootHTMLElement(preview, PREVIEW_CANCEL_SELECTOR, 'voice recording preview cancel button');
    syncAttributeValue(cancelButton, 'aria-label', actionLabelAttr);
    syncAttributeValue(cancelButton, 'data-tooltip', actionLabelAttr);
    if (preview.classList.contains(CSS_CLASSES.HIDDEN) || preview.getAttribute('aria-hidden') !== 'false') {
        setElementVisibility(context, 'voiceRecordingPreview', true);
    }
};

export { updateAudioRecordingPreview };
