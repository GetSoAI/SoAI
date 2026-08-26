/* SoAI - Conversation PDF export document controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/conversationExportPdfDocumentController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { STANDARD_LOGO_TYPES } from '@core/branding/constants.ts';
import { resolveAssetPath } from '@core/assetPaths.ts';
import { dom } from '@core/dom/dom.ts';
import { replaceChildrenFromHtml, serializeElementChildrenToHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { encodeBase64Bytes } from '@core/primitives/base64.ts';
import { escapeHtml } from '@core/security/textSanitizer.ts';
import { buildConversationExportCoverDocument, type ConversationExportCoverData } from '@features/chat/public.ts';
import { flattenConversationExportAttachmentCards } from '@pages/chat/controllers/chatmessagesendingcontroller/conversationExportPdfAttachmentCardController.ts';
import { CONVERSATION_EXPORT_PDF_STYLE } from '@pages/chat/controllers/chatmessagesendingcontroller/conversationExportPdfStyleController.ts';
import type { Conversation } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

type ConversationPdfExportDocument = {
    file: Blob;
    exportDate: string;
    smallLogoDataUri: string;
    htmlSha256: string;
    coverHtml: string;
    coverSha256: string;
};

type ConversationPdfExportBuildRequest = {
    conversation: Conversation;
    title: string;
    exportedAt: Date;
    coverData: ConversationExportCoverData;
    soaiVersion: string | null;
};

type ConversationPdfExportDocumentHost = {
    platform: {
        getDocument: () => Document;
        getRuntimeAbortSignal: () => AbortSignal | null;
    };
    services: {
        getChatApi: () => {
            fetchAsset: (path: string, options?: { timeout?: number; responseType?: 'text' | 'json' | 'blob'; signal?: AbortSignal }) => Promise<ApiResponsePayload>;
        };
        renderConversationExportMessages: (conversation: Conversation) => string;
        enhanceConversationExportInlineMedia: (container: HTMLElement, conversationId: string) => Promise<void>;
    };
};

type ImageInlineResult =
    | {
          status: 'inlined';
          dataUri: string;
      }
    | {
          status: 'failed';
      };

const IMAGE_SELECTOR = 'img';
const PLAYABLE_MEDIA_SELECTOR = 'video, audio';
const INLINE_MEDIA_CARD_SELECTOR = '.chat-inline-media-card';
const INLINE_MEDIA_CARD_MEDIA_SELECTOR = '.chat-inline-media-card__media';
const INTERACTIVE_EXPORT_UI_SELECTOR = '.message-actions,.message-action-buttons,.code-copy-btn,.loading-spinner,.chat-inline-media-card__actions,button';
const ABSOLUTE_FETCHABLE_URL_PATTERN = /^(?:https?:|blob:|data:|\/\/)/i;
const COMPACT_INLINE_MEDIA_WIDTH = 104;
const COMPACT_INLINE_MEDIA_HEIGHT = 62;

const blobToDataUri = async (blob: Blob): Promise<string> => {
    const contentType = toTrimmedString(blob.type) || 'application/octet-stream';
    return `data:${contentType};base64,${encodeBase64Bytes(new Uint8Array(await blob.arrayBuffer()))}`;
};

const fetchDataUri = async (host: ConversationPdfExportDocumentHost, url: string, signal: AbortSignal | null): Promise<string> => {
    const requestUrl = ABSOLUTE_FETCHABLE_URL_PATTERN.test(url) ? url : resolveAssetPath(url);
    if (!requestUrl) {
        throw new Error(i18n.t('chat.export.pdf.assetFetchFailed'));
    }
    const asset = await host.services.getChatApi().fetchAsset(requestUrl, signal === null ? { responseType: 'blob' } : { responseType: 'blob', signal });
    if (!(asset instanceof Blob)) {
        throw new Error(i18n.t('chat.export.pdf.assetFetchFailed'));
    }
    return await blobToDataUri(asset);
};

const digestHex = async (value: string): Promise<string> => {
    const encoded = new TextEncoder().encode(value);
    const digest = await crypto.subtle.digest('SHA-256', encoded);
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
};

const normalizeMultipartText = (value: string): string => value.replace(/\r\n|\r|\n/gu, '\r\n');

const normalizeExportImageLoading = (image: HTMLImageElement): void => {
    image.loading = 'eager';
    image.decoding = 'sync';
    image.removeAttribute('loading');
    image.removeAttribute('srcset');
};

const replaceImageWithUnavailablePlaceholder = (image: HTMLImageElement): void => {
    const documentRef = image.ownerDocument;
    const placeholder = documentRef.createElement('div');
    const label = toTrimmedString(image.alt) || i18n.t('chat.inlinePreviews.unavailableMessage');
    placeholder.className = 'chat-inline-media-card__media--placeholder chat-export-pdf-image-placeholder';
    placeholder.textContent = label;
    image.replaceWith(placeholder);
};

const waitForExportImage = async (image: HTMLImageElement): Promise<void> => {
    normalizeExportImageLoading(image);
    if (image.complete && image.naturalWidth > 0) {
        return;
    }
    const decoded = await image.decode().then(
        () => true,
        () => false
    );
    if (!decoded || image.naturalWidth <= 0) {
        replaceImageWithUnavailablePlaceholder(image);
    }
};

const waitForConversationExportAssets = async (container: HTMLElement): Promise<void> => {
    const imagePromises: Promise<void>[] = [];
    for (const element of dom.resolveAll(IMAGE_SELECTOR, container)) {
        if (element instanceof HTMLImageElement) {
            imagePromises.push(waitForExportImage(element));
        }
    }
    const fonts = container.ownerDocument.fonts;
    await Promise.all([fonts.ready, ...imagePromises]);
};

const tryInlineImage = async (host: ConversationPdfExportDocumentHost, source: string, signal: AbortSignal | null): Promise<ImageInlineResult> => {
    return await fetchDataUri(host, source, signal).then(
        (dataUri) => ({ status: 'inlined', dataUri }),
        () => ({ status: 'failed' })
    );
};

const inlineImages = async (host: ConversationPdfExportDocumentHost, container: HTMLElement, signal: AbortSignal | null): Promise<void> => {
    for (const element of dom.resolveAll(IMAGE_SELECTOR, container)) {
        if (!(element instanceof HTMLImageElement)) {
            continue;
        }
        const image = element;
        const source = toTrimmedString(image.currentSrc || image.src);
        if (!source || source.startsWith('data:')) {
            continue;
        }
        const result = await tryInlineImage(host, source, signal);
        if (result.status === 'failed') {
            replaceImageWithUnavailablePlaceholder(image);
            continue;
        }
        image.src = result.dataUri;
        normalizeExportImageLoading(image);
    }
};

const replacePlayableMedia = (container: HTMLElement): void => {
    for (const element of dom.resolveAll(PLAYABLE_MEDIA_SELECTOR, container)) {
        if (!(element instanceof HTMLMediaElement)) {
            continue;
        }
        const media = element;
        const documentRef = media.ownerDocument;
        const card = documentRef.createElement('div');
        const typeLabel = media.tagName.toLowerCase() === 'video' ? i18n.t('chat.export.pdf.video') : i18n.t('chat.export.pdf.audio');
        const source = toTrimmedString(media.currentSrc || media.src);
        const mediaFrame = documentRef.createElement('div');
        const footer = documentRef.createElement('div');
        const title = documentRef.createElement('span');
        card.className = 'chat-inline-media-card chat-inline-media-card--static';
        mediaFrame.className = 'chat-inline-media-card__media chat-inline-media-card__media--placeholder';
        mediaFrame.textContent = typeLabel;
        footer.className = 'chat-inline-media-card__footer';
        title.className = 'chat-inline-media-card__title';
        title.textContent = typeLabel;
        footer.appendChild(title);
        if (source) {
            const link = documentRef.createElement('a');
            link.className = 'chat-inline-media-card__subtitle';
            link.href = source;
            link.textContent = source;
            footer.appendChild(link);
        }
        card.append(mediaFrame, footer);
        media.replaceWith(card);
    }
};

const markCompactInlineMediaCards = (container: HTMLElement): void => {
    for (const element of dom.resolveAll(INLINE_MEDIA_CARD_SELECTOR, container)) {
        if (!(element instanceof HTMLElement)) {
            continue;
        }
        const mediaSlot = dom.resolve(INLINE_MEDIA_CARD_MEDIA_SELECTOR, element);
        if (!(mediaSlot instanceof HTMLElement)) {
            continue;
        }
        element.classList.add('chat-export-inline-media-card--media');
        for (const mediaElement of dom.resolveAll('img:not(.chat-inline-media-card__image--blurred-bg), video', mediaSlot)) {
            if (mediaElement instanceof HTMLImageElement || mediaElement instanceof HTMLVideoElement) {
                mediaElement.width = COMPACT_INLINE_MEDIA_WIDTH;
                mediaElement.height = COMPACT_INLINE_MEDIA_HEIGHT;
            }
        }
    }
};

const removeInteractiveExportUi = (container: HTMLElement): void => {
    dom.resolveAll(INTERACTIVE_EXPORT_UI_SELECTOR, container).forEach((element) => element.remove());
};

const buildMessageDocumentHtml = (bodyHtml: string, title: string): string => {
    return ['<!doctype html><html><head><meta charset="utf-8">', `<title>${escapeHtml(title)}</title>`, `<style>${CONVERSATION_EXPORT_PDF_STYLE}</style>`, '</head><body><main class="chat-export-pdf-shell">', `<section class="chat-export-pdf-content">${bodyHtml}</section>`, '</main></body></html>'].join('');
};

const buildConversationPdfExportDocument = async (host: ConversationPdfExportDocumentHost, request: ConversationPdfExportBuildRequest): Promise<ConversationPdfExportDocument> => {
    const documentRef = host.platform.getDocument();
    const signal = host.platform.getRuntimeAbortSignal();
    const container = documentRef.createElement('div');
    container.hidden = true;
    documentRef.body.appendChild(container);
    try {
        replaceChildrenFromHtml({
            element: container,
            html: host.services.renderConversationExportMessages(request.conversation),
            context: container
        });
        await host.services.enhanceConversationExportInlineMedia(container, request.conversation.id);
        replacePlayableMedia(container);
        markCompactInlineMediaCards(container);
        flattenConversationExportAttachmentCards(container);
        removeInteractiveExportUi(container);
        await inlineImages(host, container, signal);
        await waitForConversationExportAssets(container);
        const bodyHtml = serializeElementChildrenToHtml(container);
        const html = buildMessageDocumentHtml(bodyHtml, request.title);
        const logoDataUri = await fetchDataUri(host, STANDARD_LOGO_TYPES.ui.dark, signal);
        const smallLogoDataUri = await fetchDataUri(host, STANDARD_LOGO_TYPES.small.light, signal);
        const exportDate = i18n.formatDate(request.exportedAt, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        const coverHtml = normalizeMultipartText(
            buildConversationExportCoverDocument({
                title: request.title,
                exportDate,
                logoDataUri,
                soaiVersion: request.soaiVersion,
                coverData: request.coverData
            })
        );
        return {
            file: new Blob([html], { type: 'text/html;charset=utf-8' }),
            exportDate,
            smallLogoDataUri,
            htmlSha256: await digestHex(html),
            coverHtml,
            coverSha256: await digestHex(coverHtml)
        };
    } finally {
        container.remove();
    }
};

export { buildConversationPdfExportDocument };
export type { ConversationPdfExportDocumentHost };
