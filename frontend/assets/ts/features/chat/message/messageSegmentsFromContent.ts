/* SoAI - Chat feature message segments from content [frontend/assets/ts/features/chat/message/messageSegmentsFromContent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stripSoaiPathTokensForDisplay } from '@core/soailinks/codec.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, isJsonValue, type JsonObject } from '@core/types/jsonValues.ts';
import { resolveSoaiFileSegment } from '@features/chat/message/soaiFileMessageSegment.ts';
import { resolveSoaiKnowledgeSegment } from '@features/chat/message/soaiKnowledgeMessageSegment.ts';
import { resolveSoaiPathSegment } from '@features/chat/message/soaiPathMessageSegment.ts';
import { resolveSoaiFileUnavailableSegment, resolveSoaiKnowledgeUnavailableSegment } from '@features/chat/message/soaiUnavailableMessageSegment.ts';
import type { MessageContent, MessageSegment, ToolCallSegment } from '@features/chat/message/messageSegments.ts';

const normalizeMessageContent = (content: MessageContent): Array<JsonObject | string> => {
    if (content === undefined || content === null) {
        return [];
    }
    if (isString(content)) {
        return [content];
    }
    if (isJsonArray(content)) {
        const entries: Array<JsonObject | string> = [];
        for (let index = 0; index < content.length; index += 1) {
            const entry = content[index];
            if (isString(entry)) {
                entries.push(entry);
                continue;
            }
            if (!isJsonObject(entry)) {
                throw new Error(`Message content[${String(index)}] must be a string or object`);
            }
            entries.push(entry);
        }
        return entries;
    }
    if (!isJsonObject(content)) {
        throw new Error('Message content must be a string, object, or array');
    }
    return [content];
};

const resolvePartType = (part: JsonObject, index: number): string => {
    const typeValue = part['type'];
    if (!isString(typeValue) || !typeValue.trim()) {
        throw new Error(`Message content[${String(index)}] must include a non-empty string "type"`);
    }
    return typeValue.trim().toLowerCase();
};

const resolveStrictText = (part: JsonObject, index: number, fieldName: string): string => {
    const value = part[fieldName];
    if (!isString(value)) {
        throw new Error(`Message content[${String(index)}].${fieldName} must be a string`);
    }
    return value;
};

const resolveImageUrl = (part: JsonObject, index: number): string => {
    const imageValue = part['imageUrl'];
    if (!isJsonObject(imageValue)) {
        throw new Error(`Message content[${String(index)}].imageUrl must be an object with a non-empty url`);
    }
    const urlValue = imageValue['url'];
    if (!isString(urlValue) || !urlValue.trim()) {
        throw new Error(`Message content[${String(index)}].imageUrl.url must be a non-empty string`);
    }
    return urlValue.trim();
};

const resolveToolCallSegment = (part: JsonObject): ToolCallSegment => {
    const segment: ToolCallSegment = {
        type: 'tool_call'
    };

    const nameValue = part['name'];
    if (isString(nameValue) && nameValue.trim()) {
        segment.name = nameValue.trim();
    }

    const idValue = part['id'];
    if (isString(idValue) || isNumber(idValue)) {
        segment.id = idValue;
    }

    if (isJsonValue(part['args'])) {
        segment.toolArguments = part['args'];
    }
    if (isJsonValue(part['arguments'])) {
        segment.functionArguments = part['arguments'];
    }
    if (isJsonValue(part['input'])) {
        segment.input = part['input'];
    }
    if (isJsonValue(part['parameters'])) {
        segment.parameters = part['parameters'];
    }
    if (isJsonValue(part['metadata'])) {
        segment.metadata = part['metadata'];
    }
    if (isJsonObject(part['function'])) {
        segment.function = part['function'];
    }
    return segment;
};

const isSoaiPathPart = (part: JsonObject): boolean => part['type'] === 'soai_path';

const hasSoaiPathParts = (parts: Array<JsonObject | string>): boolean => parts.some((part) => !isString(part) && isSoaiPathPart(part));

const appendTextSegment = (segments: MessageSegment[], text: string): void => {
    const displayText = stripSoaiPathTokensForDisplay(text);
    if (displayText.length > 0) {
        segments.push({ type: 'text', text: displayText, value: displayText });
    }
};

const resolveStructuredMessageSegment = (part: JsonObject, index: number, partType: string): MessageSegment => {
    if (partType === 'thinking') {
        const text = resolveStrictText(part, index, 'text');
        return { type: 'thinking', text, value: text };
    }
    if (partType === 'image_url') {
        const imageUrl = resolveImageUrl(part, index);
        const title = isString(part['title']) ? part['title'] : isString(part['alt']) ? part['alt'] : '';
        return { type: 'image', imageUrl, title };
    }
    if (partType === 'soai_file') {
        return resolveSoaiFileSegment(part, index);
    }
    if (partType === 'soai_knowledge') {
        return resolveSoaiKnowledgeSegment(part, index);
    }
    if (partType === 'soai_file_unavailable') {
        return resolveSoaiFileUnavailableSegment(part, index);
    }
    if (partType === 'soai_knowledge_unavailable') {
        return resolveSoaiKnowledgeUnavailableSegment(part, index);
    }
    if (partType === 'tool_call') {
        return resolveToolCallSegment(part);
    }
    throw new Error(`Unsupported message content type "${partType}" at index ${String(index)}`);
};

const buildSoaiPathContentSegments = (contentParts: Array<JsonObject | string>): MessageSegment[] => {
    const textParts = contentParts.filter((part) => !isString(part) && part['type'] === 'text');
    const mergedTextParts: string[] = [];
    for (const [index, part] of textParts.entries()) {
        if (isString(part)) {
            throw new Error('SoAI path text part must be an object');
        }
        mergedTextParts.push(resolveStrictText(part, index, 'text'));
    }
    const text = mergedTextParts.join('\n\n');
    const soaiParts = contentParts.filter((part) => !isString(part) && isSoaiPathPart(part));
    const segments: MessageSegment[] = [];
    const soaiSegments = soaiParts.map((part, index) => {
        if (isString(part)) {
            throw new Error('SoAI path record must be an object');
        }
        return resolveSoaiPathSegment(part, index);
    });
    appendTextSegment(segments, text);
    segments.push(...soaiSegments);
    for (const [index, part] of contentParts.entries()) {
        if (isString(part) || part['type'] === 'text' || isSoaiPathPart(part)) {
            continue;
        }
        const partType = resolvePartType(part, index);
        segments.push(resolveStructuredMessageSegment(part, index, partType));
    }
    return segments;
};

export const buildMessageContentSegments = (content: MessageContent): MessageSegment[] => {
    const contentParts = normalizeMessageContent(content);
    if (hasSoaiPathParts(contentParts)) {
        return buildSoaiPathContentSegments(contentParts);
    }
    const segments: MessageSegment[] = [];

    for (const [index, part] of contentParts.entries()) {
        if (isString(part)) {
            appendTextSegment(segments, part);
            continue;
        }

        const partType = resolvePartType(part, index);
        if (partType === 'text') {
            appendTextSegment(segments, resolveStrictText(part, index, 'text'));
            continue;
        }
        segments.push(resolveStructuredMessageSegment(part, index, partType));
    }

    return segments;
};
