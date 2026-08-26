/* SoAI - Chat feature tool result news payload [frontend/assets/ts/features/chat/message/messageview/toolResultNewsPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface NewsArticlePayload {
    image: string;
    published: string;
    source: string;
    title: string;
    url: string;
}

interface ToolResultNewsPayload {
    articleCount: number;
    articles: NewsArticlePayload[];
    country: string;
    language: string;
    query: string;
}

const MAX_NEWS_ARTICLES = 25;

const HTTP_URL_PATTERN = /^https?:\/\//i;

const readRequiredString = (record: JsonObject, key: string): string | null => {
    const value = record[key];
    if (!isString(value) || !value.trim()) {
        return null;
    }
    return value.trim();
};

const readArticleImage = (record: JsonObject): string => {
    const value = record['image'];
    if (!isString(value)) {
        return '';
    }
    const trimmed = value.trim();
    return HTTP_URL_PATTERN.test(trimmed) ? trimmed : '';
};

const readArticleEntry = (value: JsonValue | undefined): NewsArticlePayload | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const title = readRequiredString(value, 'title');
    const url = readRequiredString(value, 'url');
    const source = readRequiredString(value, 'source');
    const published = readRequiredString(value, 'published');
    if (title === null || url === null || source === null || published === null || !HTTP_URL_PATTERN.test(url)) {
        return null;
    }
    return {
        image: readArticleImage(value),
        published,
        source,
        title,
        url
    };
};

const readArticles = (value: JsonValue | undefined): NewsArticlePayload[] | null => {
    if (!isJsonArray(value)) {
        return null;
    }
    const entries = value.map(readArticleEntry).filter((entry): entry is NewsArticlePayload => entry !== null);
    return entries.length > 0 ? entries.slice(0, MAX_NEWS_ARTICLES) : null;
};

const resolveToolResultNewsPayload = (payload: JsonValue | undefined): ToolResultNewsPayload | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const query = readRequiredString(payload, 'query');
    const language = readRequiredString(payload, 'language');
    const country = readRequiredString(payload, 'country');
    const articleCount = payload['article_count'];
    const articles = readArticles(payload['articles']);
    if (query === null || language === null || country === null || !isFiniteNumber(articleCount) || articles === null) {
        return null;
    }
    return {
        articleCount,
        articles,
        country,
        language,
        query
    };
};

export { MAX_NEWS_ARTICLES, resolveToolResultNewsPayload };
export type { NewsArticlePayload, ToolResultNewsPayload };
