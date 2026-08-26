/* SoAI - WebUI chat message storage normalization [frontend/assets/ts/features/chat/storage/messageNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMessageRole } from '@core/chat/messageRoles.ts';
import { isNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import { toJsonCompatibleObject } from '@core/primitives/clone.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { normalizeChatMessageForApi } from '@features/chat/apimessagemapping/normalizeChatMessageForApi.ts';
import { serializeSoaiPathContentPart } from '@core/api/contracts/webuiSoaiPathSerialization.ts';
import type { ApiChatMessage } from '@features/chat/apimessagemapping/types.ts';
import { normalizeSoaiFileStoragePart, serializeSoaiFileContentPart } from '@features/chat/attachments/soaiFileContentPart.ts';
import { normalizeSoaiKnowledgeStoragePart } from '@features/chat/attachments/soaiKnowledgeContentPart.ts';
import { normalizeSoaiPathContentPart, normalizeSoaiPathStoragePart } from '@features/chat/attachments/soaiPathContentPart.ts';
import { normalizeSoaiUnavailableFileContentPart, normalizeSoaiUnavailableFileStoragePart, normalizeSoaiUnavailableKnowledgeContentPart, normalizeSoaiUnavailableKnowledgeStoragePart, serializeSoaiUnavailableContentPart } from '@features/chat/attachments/soaiUnavailableContentPart.ts';
import type { ChatContent, ChatContentSegment, ChatMessage, ToolCall } from '@features/chat/ChatTypes.ts';
import { serializeAssistantTimeline } from '@core/realtime/eventcontracts/assistantTimelineSerialization.ts';

const serializeToolCall = (toolCall: ToolCall): JsonObject => {
    const serialized: JsonObject = {};
    if (toolCall.id !== undefined) serialized['id'] = toolCall.id;
    if (toolCall.index !== undefined) serialized['index'] = toolCall.index;
    if (toolCall.type !== undefined) serialized['type'] = toolCall.type;
    if (toolCall.function !== undefined && toolCall.function !== null) {
        const serializedFunction: JsonObject = {};
        if (toolCall.function.name !== undefined) serializedFunction['name'] = toolCall.function.name;
        if (toolCall.function.serializedArguments !== undefined) serializedFunction['arguments'] = toolCall.function.serializedArguments;
        serialized['function'] = serializedFunction;
    }
    if (toolCall.output !== undefined) serialized['output'] = toolCall.output;
    return serialized;
};

const serializeStorageContentPart = (part: ChatContentSegment): JsonValue | null => {
    if (isString(part)) {
        return part;
    }
    if (part.type === 'text' && 'text' in part && isString(part.text)) {
        return { type: 'text', text: part.text };
    }
    if (part.type === 'image_url' && 'imageUrl' in part && isPlainObject(part.imageUrl) && isString(part.imageUrl.url)) {
        const imageUrl: JsonObject = { url: part.imageUrl.url };
        if (isString(part.imageUrl.detail)) imageUrl['detail'] = part.imageUrl.detail;
        const serialized: JsonObject = { type: 'image_url', 'image_url': imageUrl };
        if ('title' in part && isString(part.title)) serialized['title'] = part.title;
        if ('alt' in part && isString(part.alt)) serialized['alt'] = part.alt;
        return serialized;
    }
    if (part.type === 'input_audio' && 'inputAudio' in part && isJsonObject(part.inputAudio)) {
        return { type: 'input_audio', 'input_audio': part.inputAudio };
    }
    if (part.type === 'file' && 'file' in part && isJsonObject(part.file)) {
        return { type: 'file', file: part.file };
    }
    if (part.type === 'refusal' && 'refusal' in part && isString(part.refusal)) {
        return { type: 'refusal', refusal: part.refusal };
    }
    if (part.type === 'soai_path') {
        if (!isPlainObject(part)) return null;
        const normalized = normalizeSoaiPathContentPart(part);
        return normalized === null ? null : serializeSoaiPathContentPart(normalized);
    }
    if (part.type === 'soai_file' && 'attachmentId' in part && 'fileId' in part && 'filename' in part && 'mimeType' in part && 'sizeBytes' in part && 'previewType' in part && 'attachmentRevision' in part && 'createdAtMs' in part) {
        return serializeSoaiFileContentPart(part);
    }
    if (part.type === 'soai_knowledge' && 'knowledgeAttachmentId' in part && 'summaryId' in part && 'sourceType' in part && 'operationType' in part && 'title' in part && 'totalCount' in part && 'visibleCount' in part && 'hiddenCount' in part && 'statusCounts' in part && 'attachmentRevision' in part && 'firstEventId' in part && 'lastEventId' in part && 'createdAtMs' in part && 'finalizedAtMs' in part) {
        return { type: 'soai_knowledge', 'knowledge_attachment_id': part.knowledgeAttachmentId, 'summary_id': part.summaryId, 'source_type': part.sourceType, 'operation_type': part.operationType, title: part.title, 'total_count': part.totalCount, 'visible_count': part.visibleCount, 'hidden_count': part.hiddenCount, 'status_counts': toJsonCompatibleObject(part.statusCounts), 'attachment_revision': part.attachmentRevision, 'first_event_id': part.firstEventId, 'last_event_id': part.lastEventId, 'created_at_ms': part.createdAtMs, 'finalized_at_ms': part.finalizedAtMs };
    }
    if ((part.type === 'soai_file_unavailable' || part.type === 'soai_knowledge_unavailable') && isPlainObject(part)) {
        const record = toJsonCompatibleObject(part);
        const normalized = part.type === 'soai_file_unavailable' ? normalizeSoaiUnavailableFileContentPart(record) : normalizeSoaiUnavailableKnowledgeContentPart(record);
        return normalized === null ? null : serializeSoaiUnavailableContentPart(normalized);
    }
    return null;
};

const serializeStorageContent = (content: ChatContent): JsonValue | null => {
    if (content === null || isString(content)) {
        return content;
    }
    const parts = Array.isArray(content) ? content : [content];
    const serialized: JsonValue[] = [];
    for (const part of parts) {
        const serializedPart = serializeStorageContentPart(part);
        if (serializedPart === null) {
            return null;
        }
        serialized.push(serializedPart);
    }
    return serialized;
};

const appendSharedMessageMetadata = (serialized: JsonObject, message: ChatMessage | ApiChatMessage, includeGenerationSpeed: boolean): void => {
    if (message.assistantTurnAtMs !== undefined) serialized['assistant_turn_at_ms'] = message.assistantTurnAtMs;
    if (message.modelVariantIndex !== undefined) serialized['model_variant_index'] = message.modelVariantIndex;
    if (message.requestId !== undefined) serialized['request_id'] = message.requestId;
    if (message.modelId !== undefined) serialized['model_id'] = message.modelId;
    if (message.promptTokens !== undefined) serialized['prompt_tokens'] = message.promptTokens;
    if (message.completionTokens !== undefined) serialized['completion_tokens'] = message.completionTokens;
    if (message.totalTokens !== undefined) serialized['total_tokens'] = message.totalTokens;
    if (message.usageSource !== undefined) serialized['usage_source'] = message.usageSource;
    if (message.generationLatencyMs !== undefined) serialized['generation_latency_ms'] = message.generationLatencyMs;
    if (includeGenerationSpeed && message.generationSpeedTokensPerSec !== undefined) serialized['generation_speed_tokens_per_sec'] = message.generationSpeedTokensPerSec;
    if (message.finishReason !== undefined) serialized['finish_reason'] = message.finishReason;
    if (message.thinkingTailDurationMs !== undefined) serialized['thinking_tail_duration_ms'] = message.thinkingTailDurationMs;
    if (message.assistantEventTimeline !== undefined) {
        serialized['assistant_event_timeline'] = serializeAssistantTimeline(message.assistantEventTimeline);
    }
};

const serializeMessageForNormalization = (message: ChatMessage): JsonObject => {
    const serialized: JsonObject = { role: message.role };
    if (message.messageType !== undefined) serialized['message_type'] = message.messageType;
    if (message.content !== undefined) {
        const content = serializeStorageContent(message.content);
        if (content !== null) serialized['content'] = content;
    }
    if (message.timestamp !== undefined) serialized['timestamp'] = message.timestamp;
    if (message.name !== undefined) serialized['name'] = message.name;
    if (message.toolCallId !== undefined) serialized['tool_call_id'] = message.toolCallId;
    if (message.toolCalls !== undefined) serialized['tool_calls'] = message.toolCalls.map(serializeToolCall);
    appendSharedMessageMetadata(serialized, message, false);
    return serialized;
};

const serializeNormalizedApiMessage = (message: ApiChatMessage): JsonObject => {
    const serialized: JsonObject = { role: message.role, content: message.content, timestamp: message.timestamp };
    if (message.name !== undefined) serialized['name'] = message.name;
    if (message.toolCalls !== undefined) serialized['tool_calls'] = message.toolCalls.map(serializeToolCall);
    if (message.toolCallId !== undefined) serialized['tool_call_id'] = message.toolCallId;
    appendSharedMessageMetadata(serialized, message, true);
    return serialized;
};

const hasWebuiAttachmentPart = (content: JsonValue | undefined): boolean => {
    if (!isJsonArray(content)) {
        return false;
    }
    return content.some((part) => isPlainObject(part) && (part['type'] === 'soai_path' || part['type'] === 'soai_file' || part['type'] === 'soai_knowledge' || part['type'] === 'soai_file_unavailable' || part['type'] === 'soai_knowledge_unavailable'));
};

const normalizeStorageContentPart = (part: JsonValue): JsonValue | null => {
    if (!isPlainObject(part)) {
        return null;
    }
    const typeValue = part['type'];
    if (!isString(typeValue) || !typeValue.trim()) {
        return null;
    }
    const type = typeValue.trim();
    if (type === 'text') {
        const textValue = part['text'];
        return isString(textValue) ? { type: 'text', text: textValue } : null;
    }
    if (type === 'soai_path') {
        const normalized = isJsonObject(part) ? normalizeSoaiPathStoragePart(part) : null;
        return normalized ? serializeStorageContentPart(normalized) : null;
    }
    if (type === 'soai_file') {
        const normalized = isJsonObject(part) ? normalizeSoaiFileStoragePart(part) : null;
        return normalized ? serializeStorageContentPart(normalized) : null;
    }
    if (type === 'soai_knowledge') {
        const normalized = isJsonObject(part) ? normalizeSoaiKnowledgeStoragePart(part) : null;
        return normalized ? serializeStorageContentPart(normalized) : null;
    }
    if (type === 'soai_file_unavailable' || type === 'soai_knowledge_unavailable') {
        const normalized = type === 'soai_file_unavailable' ? normalizeSoaiUnavailableFileStoragePart(part) : normalizeSoaiUnavailableKnowledgeStoragePart(part);
        return normalized ? serializeSoaiUnavailableContentPart(normalized) : null;
    }
    if (type === 'image_url' || type === 'input_audio' || type === 'file' || type === 'refusal') {
        return toJsonCompatibleObject(part);
    }
    return null;
};

const normalizeStorageContent = (content: JsonValue | undefined): JsonValue | null => {
    if (isString(content)) {
        return content;
    }
    if (!isJsonArray(content)) {
        return null;
    }
    const normalized: JsonValue[] = [];
    for (const part of content) {
        const normalizedPart = normalizeStorageContentPart(part);
        if (normalizedPart === null) {
            return null;
        }
        normalized.push(normalizedPart);
    }
    return normalized;
};

const normalizeChatMessageForBackendStorage = (message: ChatMessage): JsonObject | null => {
    if (message.assistantTimelineType === 'projection') {
        throw new Error('Projected assistant timelines cannot be persisted.');
    }
    const serializedMessage = serializeMessageForNormalization(message);
    const strictOpenAiMessage = normalizeChatMessageForApi(serializedMessage);
    if (strictOpenAiMessage !== null) {
        const normalizedOpenAiMessage = serializeNormalizedApiMessage(strictOpenAiMessage);
        if (serializedMessage['message_type'] !== undefined) normalizedOpenAiMessage['message_type'] = serializedMessage['message_type'];
        const roleValue = strictOpenAiMessage.role;
        const timestampValue = strictOpenAiMessage.timestamp;
        if (!isString(roleValue) || !isMessageRole(roleValue) || !isNumber(timestampValue)) {
            return null;
        }
        return normalizedOpenAiMessage;
    }
    if (!hasWebuiAttachmentPart(serializedMessage['content'])) {
        return null;
    }
    const roleValue = serializedMessage['role'];
    const role = isString(roleValue) ? roleValue.trim() : '';
    if (!isMessageRole(role)) {
        return null;
    }
    const timestampValue = serializedMessage['timestamp'];
    if (!isNumber(timestampValue) || !Number.isFinite(timestampValue) || !Number.isInteger(timestampValue)) {
        return null;
    }
    const content = normalizeStorageContent(serializedMessage['content']);
    if (content === null) {
        return null;
    }
    const normalized: JsonObject = {
        role,
        content,
        timestamp: timestampValue
    };
    return normalized;
};

export { normalizeChatMessageForBackendStorage, normalizeSoaiPathStoragePart, serializeStorageContentPart };
