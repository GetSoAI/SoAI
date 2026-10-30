/* SoAI - Chat attachment dialog thumbnail and status presentation [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachDraftPresentationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { createSpeechMediaSelectionView } from '@core/speechsetup/selectionView.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { AttachDraftDisplayRecord, AttachDraftEntry, AttachDraftListElements, AttachDraftPresentation } from '@features/attachmodal/public.ts';
import { hasAttachmentThumbnail, preserveStableAttachmentThumbnailVisuals, prepareAttachmentThumbnailLifecycles, resolveDraftAttachmentStatusLabel } from '@features/chat/public.ts';

const resolveDraftAttachmentStatusPresentation = (attachment: AttachDraftDisplayRecord): { label: string; className: string } => {
    if (attachment.parseStatus === 'ready' && attachment.missingCapabilities?.includes('speech_to_text')) {
        return { label: i18n.t('chat.configuration.rag.status.noTranscript'), className: 'status-orange' };
    }
    if (attachment.parseStatus === 'ready') {
        return { label: resolveDraftAttachmentStatusLabel(attachment.parseStatus), className: 'status-green' };
    }
    if (attachment.parseStatus === 'processing') {
        return { label: resolveDraftAttachmentStatusLabel(attachment.parseStatus), className: 'status-blue' };
    }
    return { label: resolveDraftAttachmentStatusLabel(attachment.parseStatus), className: 'status-red' };
};

const createDraftAttachmentVisual = (documentRef: Document, entry: AttachDraftEntry): HTMLElement => {
    const icon = documentRef.createElement('span');
    icon.className = 'file-preview-leading-icon';
    icon.setAttribute('aria-hidden', 'true');
    replaceChildrenFromTrustedHtml({ element: icon, html: getIconSync(entry.iconName, { size: 20, strokeWidth: 1.5 }), context: icon });
    if (!entry.attachment.isImage) {
        return icon;
    }
    const visual = documentRef.createElement('span');
    visual.className = 'chat-attachment-visual';
    visual.setAttribute('data-attachment-image-state', entry.previewUrl === null ? 'error' : 'loading');
    visual.setAttribute('data-attachment-processing-state', entry.attachment.parseStatus);
    visual.append(icon);
    if (entry.previewUrl !== null) {
        const image = documentRef.createElement('img');
        image.src = entry.previewUrl;
        image.alt = '';
        image.loading = 'lazy';
        image.decoding = 'async';
        image.setAttribute('data-chat-attachment-thumbnail', 'true');
        visual.append(image);
    }
    if (entry.attachment.parseStatus === 'processing') {
        const overlay = documentRef.createElement('span');
        overlay.className = 'file-preview-image-loading';
        overlay.setAttribute('aria-hidden', 'true');
        const spinner = documentRef.createElement('span');
        spinner.className = 'loading-spinner file-preview-image-spinner';
        spinner.setAttribute('aria-hidden', 'true');
        overlay.append(spinner);
        visual.append(overlay);
    }
    return visual;
};

const createChatDraftPresentation = (elements: AttachDraftListElements, signal: AbortSignal): AttachDraftPresentation => {
    const speech = createSpeechMediaSelectionView(elements.summary, signal);
    return {
        status: resolveDraftAttachmentStatusPresentation,
        createVisual: createDraftAttachmentVisual,
        preserveVisuals: (current, next) => preserveStableAttachmentThumbnailVisuals(current, next, 'clone') > 0,
        hasThumbnails: hasAttachmentThumbnail,
        prepareThumbnails: prepareAttachmentThumbnailLifecycles,
        afterRender: (entries) =>
            speech(
                entries.map((entry) => entry.attachment.mimeType ?? entry.attachment.type),
                entries.some((entry) => entry.attachment.missingCapabilities?.includes('speech_to_text'))
            )
    };
};

export { createChatDraftPresentation };
