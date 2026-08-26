/* SoAI - Chat feature assistant news article detail [frontend/assets/ts/features/chat/message/messageview/assistantNewsArticleDetail.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildMediaProxyUrl } from '@core/api/endpoints/webuiPreviewPaths.ts';
import { i18n } from '@core/i18n/index.ts';
import { isAbsoluteHttpUrl } from '@core/security/public.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';
import type { NewsArticlePayload } from '@features/chat/message/messageview/toolResultNewsPayload.ts';
import { NEWS_LINK_ICON_OPTIONS, NEWS_PLACEHOLDER_ICON_OPTIONS } from '@features/chat/message/messageview/assistantNewsIcons.ts';
import { formatNewsSourceLabel, formatPublishedDetailLabel } from '@features/chat/message/messageview/assistantNewsFormatters.ts';

const resolveArticleImageSource = (host: ChatMessageRenderHost, imageUrl: string): string | null => {
    const sanitizedImage = host.sanitizeImage(imageUrl);
    if (sanitizedImage === null) {
        return null;
    }
    if (!isAbsoluteHttpUrl(sanitizedImage)) {
        return sanitizedImage;
    }
    return host.sanitizeImage(buildMediaProxyUrl(sanitizedImage, false));
};

const renderArticleMedia = (host: ChatMessageRenderHost, article: NewsArticlePayload): string => {
    const placeholderIcon = host.getIconHtml('file-image', NEWS_PLACEHOLDER_ICON_OPTIONS);
    const placeholder = `<span class="assistant-news-widget__media-placeholder" aria-hidden="true">${placeholderIcon}</span>`;
    const imageSourceValue = article.image === '' ? null : resolveArticleImageSource(host, article.image);
    if (imageSourceValue === null) {
        const noImageLabel = host.escapeAttribute(i18n.t('chat.news.noImage'));
        return `<div class="assistant-news-widget__media" data-empty="true" role="img" aria-label="${noImageLabel}">${placeholder}</div>`;
    }
    const imageSource = host.escapeAttribute(imageSourceValue);
    const image = ['<img class="assistant-news-widget__image"', ` src="${imageSource}"`, ' alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">'].join('');
    return `<div class="assistant-news-widget__media" data-image-state="loading">${placeholder}${image}</div>`;
};

const renderArticleDetailMeta = (host: ChatMessageRenderHost, article: NewsArticlePayload): string => {
    const source = host.escapeHtml(formatNewsSourceLabel(article.source));
    const published = host.escapeHtml(formatPublishedDetailLabel(article.published));
    return ['<div class="assistant-news-widget__detail-meta">', `<span class="assistant-news-widget__source">${source}</span>`, `<span class="assistant-news-widget__published">${published}</span>`, '</div>'].join('');
};

const renderArticleLink = (host: ChatMessageRenderHost, article: NewsArticlePayload): string => {
    const labelText = i18n.t('contentPreview.actions.openSource');
    const linkLabel = host.escapeHtml(labelText);
    const labelAttribute = host.escapeAttribute(labelText);
    const linkIcon = host.getIconHtml('external-link', NEWS_LINK_ICON_OPTIONS);
    const linkUrl = host.escapeAttribute(article.url);
    return `<a class="assistant-news-widget__link ui-button ui-button--sm ui-variant-neutral external-link-confirmation" href="${linkUrl}" data-href="${linkUrl}" target="_blank" rel="noopener noreferrer" aria-label="${labelAttribute}" data-tooltip="${labelAttribute}"><span class="assistant-news-widget__link-icon">${linkIcon}</span><span>${linkLabel}</span></a>`;
};

const renderNewsArticlePanel = (host: ChatMessageRenderHost, article: NewsArticlePayload, isSelected: boolean, radioId: string, radioGroupName: string): string => {
    const checked = isSelected ? ' checked' : '';
    const radio = `<input class="assistant-news-widget__item-selector visually-hidden" type="radio" id="${host.escapeAttribute(radioId)}" name="${host.escapeAttribute(radioGroupName)}"${checked}>`;
    const media = renderArticleMedia(host, article);
    const title = `<h3 class="assistant-news-widget__detail-title">${host.escapeHtml(article.title)}</h3>`;
    const meta = renderArticleDetailMeta(host, article);
    const link = renderArticleLink(host, article);
    return [radio, '<div class="assistant-news-widget__detail-panel">', media, title, meta, link, '</div>'].join('');
};

export { renderNewsArticlePanel };
