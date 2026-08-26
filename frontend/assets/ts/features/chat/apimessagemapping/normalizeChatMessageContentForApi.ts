/* SoAI - API normalization of chat message content [frontend/assets/ts/features/chat/apimessagemapping/normalizeChatMessageContentForApi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type ApiMessageContentPart = { type: 'text'; text: string } | { type: 'image_url'; imageUrl: { url: string; detail?: 'auto' | 'low' | 'high' } } | { type: 'input_audio'; inputAudio: { data: string; format: 'wav' | 'mp3' } };

const resolveImageDetail = (value: JsonValue | undefined): 'auto' | 'low' | 'high' | null => {
    if (!isString(value)) {
        return null;
    }
    const normalized = value.trim().toLowerCase();
    if (normalized === 'auto' || normalized === 'low' || normalized === 'high') {
        return normalized;
    }
    return null;
};

const resolveImageUrlPart = (record: JsonObject): Extract<ApiMessageContentPart, { type: 'image_url' }> | null => {
    const imageUrlValue = record['image_url'];
    if (!isJsonObject(imageUrlValue)) {
        return null;
    }
    const urlValue = imageUrlValue['url'];
    if (!isString(urlValue) || !urlValue.trim()) {
        return null;
    }
    const detailValue = imageUrlValue['detail'];
    if (detailValue !== undefined) {
        const detail = resolveImageDetail(detailValue);
        if (detail === null) {
            return null;
        }
        return {
            type: 'image_url',
            imageUrl: {
                url: urlValue.trim(),
                detail
            }
        };
    }
    return {
        type: 'image_url',
        imageUrl: {
            url: urlValue.trim()
        }
    };
};

const resolveInputAudioPart = (record: JsonObject): Extract<ApiMessageContentPart, { type: 'input_audio' }> | null => {
    const inputAudioValue = record['input_audio'];
    if (!isJsonObject(inputAudioValue)) {
        return null;
    }
    const dataValue = inputAudioValue['data'];
    const formatValue = inputAudioValue['format'];
    if (!isString(dataValue) || !dataValue.trim()) {
        return null;
    }
    if (!isString(formatValue)) {
        return null;
    }
    const normalizedFormat = formatValue.trim().toLowerCase();
    if (normalizedFormat !== 'wav' && normalizedFormat !== 'mp3') {
        return null;
    }
    return {
        type: 'input_audio',
        inputAudio: {
            data: dataValue,
            format: normalizedFormat
        }
    };
};

const normalizeMessageContentPartForApi = (part: JsonValue): ApiMessageContentPart | null => {
    if (!isJsonObject(part)) {
        return null;
    }
    const typeValue = part['type'];
    if (!isString(typeValue) || !typeValue.trim()) {
        return null;
    }
    const normalizedType = typeValue.trim().toLowerCase();
    if (normalizedType === 'text') {
        const textValue = part['text'];
        if (!isString(textValue) || !textValue.trim()) {
            return null;
        }
        return {
            type: 'text',
            text: textValue
        };
    }
    if (normalizedType === 'image_url') {
        return resolveImageUrlPart(part);
    }
    if (normalizedType === 'input_audio') {
        return resolveInputAudioPart(part);
    }
    return null;
};

const normalizeMessageContentForApi = (content: JsonValue | undefined): string | JsonValue[] | null => {
    if (content === undefined || content === null) {
        return null;
    }
    if (isString(content)) {
        return content;
    }
    if (isJsonArray(content)) {
        const normalizedParts: JsonValue[] = [];
        for (const part of content) {
            const normalizedPart = normalizeMessageContentPartForApi(part);
            if (normalizedPart === null) {
                return null;
            }
            normalizedParts.push(normalizedPart);
        }
        return normalizedParts;
    }
    if (isJsonObject(content)) {
        const normalizedPart = normalizeMessageContentPartForApi(content);
        return normalizedPart !== null ? [normalizedPart] : null;
    }
    return null;
};

export { normalizeMessageContentForApi };
