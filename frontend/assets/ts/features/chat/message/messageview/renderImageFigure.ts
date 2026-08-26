/* SoAI - Chat feature render image figure [frontend/assets/ts/features/chat/message/messageview/renderImageFigure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { InlineMediaOpenAction } from '@features/chat/message/enhancers/inlineMultimediaCardTypes.ts';
import { renderChatMultimediaPreviewOpenActionAttributes, resolveChatMultimediaPreviewSourceReferenceForUrl } from '@features/chat/message/multimediaPreviewDataset.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';

interface ImageFigureRenderInput {
    allowEmptyLabel?: boolean;
    className?: string;
    contentLength?: number | null;
    contentType?: string | null;
    downloadName?: string;
    label?: string;
    loading?: 'eager' | 'lazy';
    src: string;
}

const renderImageFigure = (host: ChatMessageRenderHost, input: ImageFigureRenderInput): string => {
    const sanitizedUrl = host.sanitizeImage(input.src);
    if (!sanitizedUrl) {
        return '';
    }
    const explicitLabel = input.label?.trim() ? input.label.trim() : '';
    const allowEmptyLabel = input.allowEmptyLabel === true;
    const label = explicitLabel || (allowEmptyLabel ? '' : i18n.t('chat.message.generatedImage'));
    const className = input.className?.trim() ? input.className.trim() : 'message-image';
    const downloadName = input.downloadName?.trim() ? input.downloadName.trim() : 'soai-image.png';
    const alt = host.escapeAttribute(label);
    const src = host.escapeAttribute(sanitizedUrl);
    const classes = host.escapeAttribute(className);
    const loading = input.loading === 'eager' ? 'eager' : 'lazy';
    const openAction: InlineMediaOpenAction = {
        type: 'image',
        previewUrl: sanitizedUrl,
        openSourceUrl: sanitizedUrl,
        title: label,
        downloadName,
        downloadUrl: null,
        contentType: input.contentType ?? null,
        contentLength: input.contentLength ?? null,
        sourceReference: resolveChatMultimediaPreviewSourceReferenceForUrl(sanitizedUrl),
        requireMetadata: false
    };
    const actionAttributes = renderChatMultimediaPreviewOpenActionAttributes(openAction);
    const image = `<img src="${src}" alt="${alt}" loading="${loading}" decoding="async"${actionAttributes.html}/>`;
    return `<figure class="${classes}">${image}</figure>`;
};

export { renderImageFigure };
