/* SoAI - Chat feature assistant news widget [frontend/assets/ts/features/chat/message/messageview/assistantNewsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ChatMessageRenderHost, MessageSegment } from '@features/chat/message/messageview/types.ts';
import { resolveToolResultNewsPayload, type NewsArticlePayload, type ToolResultNewsPayload } from '@features/chat/message/messageview/toolResultNewsPayload.ts';
import { NEWS_HEADER_ICON_OPTIONS } from '@features/chat/message/messageview/assistantNewsIcons.ts';
import { renderAssistantActivityWidgetFooter } from '@features/chat/message/messageview/assistantActivityWidgetFooter.ts';
import { renderNewsArticlePanel } from '@features/chat/message/messageview/assistantNewsArticleDetail.ts';
import { formatNewsArticleCount, formatNewsArticleOrdinal, formatNewsScopeToken, formatNewsSourceLabel, formatPublishedDayLabel } from '@features/chat/message/messageview/assistantNewsFormatters.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

const NEWS_TOOL_NAME = 'news';

const renderNewsListItem = (host: ChatMessageRenderHost, article: NewsArticlePayload, articleIndex: number, radioId: string): string => {
    const ordinal = host.escapeHtml(formatNewsArticleOrdinal(articleIndex));
    const title = host.escapeHtml(article.title);
    const source = host.escapeHtml(formatNewsSourceLabel(article.source));
    const dayLabel = host.escapeHtml(formatPublishedDayLabel(article.published));
    return [`<label class="assistant-news-widget__item" for="${host.escapeAttribute(radioId)}">`, `<span class="assistant-news-widget__item-index">${ordinal}</span>`, `<span class="assistant-news-widget__item-title">${title}</span>`, `<span class="assistant-news-widget__item-meta">${source} &middot; ${dayLabel}</span>`, '</label>'].join('');
};

const renderNewsScope = (host: ChatMessageRenderHost, payload: ToolResultNewsPayload): string => {
    const language = host.escapeHtml(formatNewsScopeToken(payload.language));
    const country = host.escapeHtml(formatNewsScopeToken(payload.country));
    const countLabel = host.escapeHtml(i18n.t('chat.news.articleCount', { count: formatNewsArticleCount(payload.articles.length) }));
    return `${language} &middot; ${country} &middot; ${countLabel}`;
};

const renderNewsHeader = (host: ChatMessageRenderHost, payload: ToolResultNewsPayload): string => {
    const headerIcon = host.getIconHtml('news', NEWS_HEADER_ICON_OPTIONS);
    const label = host.escapeHtml(i18n.t('chat.news.label'));
    const query = host.escapeHtml(payload.query);
    const scope = renderNewsScope(host, payload);
    return ['<header class="assistant-news-widget__header">', '<span class="assistant-news-widget__title">', `<span class="assistant-news-widget__title-icon">${headerIcon}</span>`, `<span class="assistant-news-widget__label">${label}</span>`, `<span class="assistant-news-widget__query">${query}</span>`, '</span>', `<span class="assistant-news-widget__scope">${scope}</span>`, '</header>'].join('');
};

const renderNewsWidget = (host: ChatMessageRenderHost, payload: ToolResultNewsPayload, callId: string, startedAtMs: number | undefined): string => {
    const radioGroupName = `news-article-${callId}`;
    const items = payload.articles.map((article, index) => renderNewsListItem(host, article, index, `news-article-${callId}-${String(index)}`)).join('');
    const panels = payload.articles.map((article, index) => renderNewsArticlePanel(host, article, index === 0, `news-article-${callId}-${String(index)}`, radioGroupName)).join('');
    const ariaLabel = host.escapeAttribute(i18n.t('chat.news.label'));
    const articlesLabel = host.escapeAttribute(i18n.t('chat.news.articles'));
    return [`<section class="assistant-news-widget" aria-label="${ariaLabel}">`, renderNewsHeader(host, payload), '<div class="assistant-news-widget__body">', `<nav class="assistant-news-widget__list" aria-label="${articlesLabel}">${items}</nav>`, `<div class="assistant-news-widget__detail">${panels}</div>`, '</div>', renderAssistantActivityWidgetFooter(host, startedAtMs), '</section>'].join('');
};

const renderAssistantNewsWidget = (host: ChatMessageRenderHost, segment: MessageSegment): string => {
    if (segment.type !== 'inline_tool_activity') {
        return '';
    }
    const toolLeafName = normalizeToolLeafName(segment.toolName);
    if (segment.status !== 'completed' || toolLeafName !== NEWS_TOOL_NAME) {
        return '';
    }
    const payload = resolveToolResultNewsPayload(segment.result);
    if (payload === null) {
        return '';
    }
    return renderNewsWidget(host, payload, segment.callId, segment.startedAtMs);
};

export { renderAssistantNewsWidget };
