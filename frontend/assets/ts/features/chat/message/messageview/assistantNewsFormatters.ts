/* SoAI - Chat feature assistant news formatters [frontend/assets/ts/features/chat/message/messageview/assistantNewsFormatters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatLocalizedDate, formatLocalizedNumber } from '@core/localization/public.ts';

const parsePublishedDate = (publishedValue: string): Date | null => {
    const timestamp = new Date(publishedValue).getTime();
    if (!Number.isFinite(timestamp)) {
        return null;
    }
    return new Date(timestamp);
};

const formatPublishedDayLabel = (publishedValue: string): string => {
    const parsed = parsePublishedDate(publishedValue);
    if (parsed === null) {
        return publishedValue;
    }
    return formatLocalizedDate(parsed, { month: 'short', day: 'numeric' });
};

const formatPublishedDetailLabel = (publishedValue: string): string => {
    const parsed = parsePublishedDate(publishedValue);
    if (parsed === null) {
        return publishedValue;
    }
    const dateLabel = formatLocalizedDate(parsed, { month: 'short', day: 'numeric', year: 'numeric' });
    const timeLabel = formatLocalizedDate(parsed, { hour: 'numeric', minute: '2-digit' });
    return `${dateLabel} · ${timeLabel}`;
};

const formatNewsSourceLabel = (sourceValue: string): string => {
    const normalized = sourceValue.trim().toLowerCase();
    return normalized.startsWith('www.') ? normalized.slice(4) : normalized;
};

const formatNewsArticleOrdinal = (articleIndex: number): string => formatLocalizedNumber(articleIndex + 1, { minimumIntegerDigits: 2, maximumFractionDigits: 0, useGrouping: false });

const formatNewsArticleCount = (articleCount: number): string => formatLocalizedNumber(articleCount, { maximumFractionDigits: 0 });

const formatNewsScopeToken = (scopeValue: string): string => scopeValue.trim().toUpperCase();

export { formatNewsArticleCount, formatNewsArticleOrdinal, formatNewsScopeToken, formatNewsSourceLabel, formatPublishedDayLabel, formatPublishedDetailLabel };
