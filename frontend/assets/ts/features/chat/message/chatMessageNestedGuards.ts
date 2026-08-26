/* SoAI - Runtime guards for nested chat message values [frontend/assets/ts/features/chat/message/chatMessageNestedGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonArray, isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { normalizeSoaiFileContentPart } from '@features/chat/attachments/soaiFileContentPart.ts';
import { normalizeSoaiPathContentPart } from '@features/chat/attachments/soaiPathContentPart.ts';
import { normalizeSoaiUnavailableFileContentPart, normalizeSoaiUnavailableKnowledgeContentPart } from '@features/chat/attachments/soaiUnavailableContentPart.ts';

const isFiniteNumber = (value: JsonValue | undefined): value is number => typeof value === 'number' && Number.isFinite(value);
const isOptionalFiniteNumber = (value: JsonValue | undefined): boolean => value === undefined || isFiniteNumber(value);
const isOptionalString = (value: JsonValue | undefined): boolean => value === undefined || typeof value === 'string';
const isOptionalNullableString = (value: JsonValue | undefined): boolean => value === undefined || value === null || typeof value === 'string';
const isOptionalBoolean = (value: JsonValue | undefined): boolean => value === undefined || typeof value === 'boolean';

const isToolFunctionCall = (value: JsonValue | undefined): boolean => {
    if (!isJsonObject(value)) {
        return false;
    }
    return isOptionalString(value['name']) && isOptionalString(value['serializedArguments']);
};

const isOptionalImageReference = (value: JsonValue | undefined): boolean => {
    if (value === undefined || typeof value === 'string') {
        return true;
    }
    return isJsonObject(value) && isOptionalString(value['url']) && isOptionalString(value['detail']) && isOptionalString(value['previewUrl']);
};

const isStructuredContentSegment = (value: JsonObject): boolean => {
    const type = value['type'];
    if (type === 'text' || type === 'thinking') {
        return isOptionalString(value['text']) && isOptionalString(value['value']);
    }
    if (type === 'image' || type === 'image_url') {
        return isOptionalImageReference(value['imageUrl']) && isOptionalImageReference(value['image']) && isOptionalString(value['url']) && isOptionalString(value['src']) && isOptionalString(value['title']) && isOptionalString(value['alt']);
    }
    if (type !== 'tool_call') {
        return false;
    }
    const functionValue = value['function'];
    return isOptionalString(value['id']) && isOptionalString(value['name']) && (functionValue === undefined || isToolFunctionCall(functionValue)) && (value['metadata'] === undefined || isJsonObject(value['metadata']));
};

const isNullableFiniteNumber = (value: JsonValue | undefined): boolean => value === null || isFiniteNumber(value);

const isKnowledgeContentSegment = (value: JsonObject): boolean => {
    const statusCounts = value['statusCounts'];
    return typeof value['knowledgeAttachmentId'] === 'string' && typeof value['summaryId'] === 'string' && typeof value['sourceType'] === 'string' && typeof value['operationType'] === 'string' && typeof value['title'] === 'string' && isFiniteNumber(value['totalCount']) && isFiniteNumber(value['visibleCount']) && isFiniteNumber(value['hiddenCount']) && isJsonObject(statusCounts) && Object.values(statusCounts).every(isFiniteNumber) && isFiniteNumber(value['attachmentRevision']) && isNullableFiniteNumber(value['firstEventId']) && isNullableFiniteNumber(value['lastEventId']) && isFiniteNumber(value['createdAtMs']) && isFiniteNumber(value['finalizedAtMs']);
};

const isWebuiContentSegment = (value: JsonObject): boolean => {
    if (value['type'] === 'input_audio') {
        return isJsonObject(value['inputAudio']);
    }
    if (value['type'] === 'file') {
        return isJsonObject(value['file']);
    }
    if (value['type'] === 'refusal') {
        return typeof value['refusal'] === 'string';
    }
    if (value['type'] === 'soai_file') {
        return normalizeSoaiFileContentPart(value) !== null;
    }
    if (value['type'] === 'soai_path') {
        return normalizeSoaiPathContentPart(value) !== null;
    }
    if (value['type'] === 'soai_file_unavailable') {
        return normalizeSoaiUnavailableFileContentPart(value) !== null;
    }
    if (value['type'] === 'soai_knowledge_unavailable') {
        return normalizeSoaiUnavailableKnowledgeContentPart(value) !== null;
    }
    return value['type'] === 'soai_knowledge' && isKnowledgeContentSegment(value);
};

const isChatContentSegment = (value: JsonValue): boolean => {
    if (typeof value === 'string') {
        return true;
    }
    return isJsonObject(value) && (isStructuredContentSegment(value) || isWebuiContentSegment(value));
};

const isChatContent = (value: JsonValue | undefined): boolean => {
    if (value === undefined || value === null || typeof value === 'string') {
        return true;
    }
    if (isJsonArray(value)) {
        return value.every(isChatContentSegment);
    }
    return isChatContentSegment(value);
};

const isToolCall = (value: JsonValue): boolean => {
    if (!isJsonObject(value)) {
        return false;
    }
    const identifier = value['id'];
    const functionValue = value['function'];
    return (identifier === undefined || identifier === null || typeof identifier === 'string') && isOptionalFiniteNumber(value['index']) && isOptionalString(value['type']) && (functionValue === undefined || functionValue === null || isToolFunctionCall(functionValue)) && isOptionalString(value['output']) && (value['toolArguments'] === undefined || isJsonValue(value['toolArguments'])) && (value['functionArguments'] === undefined || isJsonValue(value['functionArguments'])) && (value['input'] === undefined || isJsonValue(value['input'])) && (value['parameters'] === undefined || isJsonValue(value['parameters']));
};

const isToolCallArray = (value: JsonValue | undefined): boolean => value === undefined || (isJsonArray(value) && value.every(isToolCall));

const isAssistantTimelineItem = (value: JsonValue): boolean => {
    if (!isJsonObject(value)) {
        return false;
    }
    return isFiniteNumber(value['sequence']) && isFiniteNumber(value['assistantRevision']) && typeof value['eventType'] === 'string' && isJsonObject(value['payload']);
};

const isAssistantTimeline = (value: JsonValue | undefined): boolean => value === undefined || (isJsonArray(value) && value.every(isAssistantTimelineItem));

const isToolActivityCodeDiff = (value: JsonValue): boolean => {
    if (!isJsonObject(value)) {
        return false;
    }
    return typeof value['path'] === 'string' && typeof value['operation'] === 'string' && typeof value['diff'] === 'string' && typeof value['truncated'] === 'boolean';
};

const isToolActivityStatus = (value: JsonValue | undefined): boolean => value === 'pending' || value === 'running' || value === 'completed' || value === 'cancelled' || value === 'error';

const isToolActivityItem = (value: JsonValue): boolean => {
    if (!isJsonObject(value)) {
        return false;
    }
    const codeDiffs = value['codeDiffs'];
    const syncStatus = value['syncStatus'];
    return (
        typeof value['callId'] === 'string' &&
        typeof value['toolName'] === 'string' &&
        isToolActivityStatus(value['status']) &&
        isOptionalFiniteNumber(value['signatureSequence']) &&
        (value['inputArguments'] === undefined || isJsonValue(value['inputArguments'])) &&
        (codeDiffs === undefined || (isJsonArray(codeDiffs) && codeDiffs.every(isToolActivityCodeDiff))) &&
        (value['result'] === undefined || isJsonValue(value['result'])) &&
        isOptionalString(value['error']) &&
        isOptionalFiniteNumber(value['durationMs']) &&
        isOptionalFiniteNumber(value['startedAtMs']) &&
        isOptionalFiniteNumber(value['completedAtMs']) &&
        isOptionalFiniteNumber(value['liveRevision']) &&
        isOptionalFiniteNumber(value['lastLiveSequence']) &&
        isOptionalFiniteNumber(value['lastLiveEventAtMs']) &&
        (syncStatus === undefined || syncStatus === 'in_sync' || syncStatus === 'out_of_sync') &&
        isOptionalFiniteNumber(value['thinkingDurationBeforeMs']) &&
        isFiniteNumber(value['sequenceIndex']) &&
        isFiniteNumber(value['contentIndexBefore']) &&
        isFiniteNumber(value['thinkingIndexBefore']) &&
        typeof value['collapsed'] === 'boolean'
    );
};

const isToolActivityArray = (value: JsonValue | undefined): boolean => value === undefined || (isJsonArray(value) && value.every(isToolActivityItem));

const isContentPreviewFeedbackState = (value: JsonValue | undefined): boolean => {
    if (value === undefined) {
        return true;
    }
    if (!isJsonObject(value) || !isJsonArray(value['items'])) {
        return false;
    }
    return (
        isFiniteNumber(value['assistantAtMs']) &&
        isFiniteNumber(value['assistantTurnAtMs']) &&
        value['items'].every((item) => {
            if (!isJsonObject(item)) {
                return false;
            }
            const referenceType = item['referenceType'];
            const status = item['status'];
            const reasonCode = item['reasonCode'];
            return (referenceType === 'absolute_path' || referenceType === 'virtual_path' || referenceType === 'remote_url') && typeof item['target'] === 'string' && (status === 'failed' || status === 'disabled') && (reasonCode === 'not_found' || reasonCode === 'access_denied' || reasonCode === 'invalid_reference' || reasonCode === 'request_failed' || reasonCode === 'upstream_not_found' || reasonCode === 'upstream_gone' || reasonCode === 'unsupported' || reasonCode === 'previews_disabled');
        }) &&
        typeof value['pendingForModel'] === 'boolean'
    );
};

const isCompactionPromptMessage = (value: JsonValue | undefined): boolean => {
    if (!isJsonObject(value)) {
        return false;
    }
    return typeof value['role'] === 'string' && typeof value['content'] === 'string' && isOptionalString(value['name']);
};

const isSoaiCompactionMarker = (value: JsonValue | undefined): boolean => {
    if (value === undefined) {
        return true;
    }
    if (!isJsonObject(value)) {
        return false;
    }
    const details = value['details'];
    const promptMessage = value['promptMessage'];
    return isOptionalNullableString(value['toolCallId']) && isOptionalString(value['status']) && isOptionalNullableString(value['output']) && isOptionalNullableString(value['trigger']) && isOptionalNullableString(value['model']) && (details === undefined || isJsonObject(details)) && (promptMessage === undefined || isCompactionPromptMessage(promptMessage)) && isOptionalFiniteNumber(value['boundaryRemovedAtMs']) && isOptionalString(value['boundaryRemovedReason']) && isOptionalFiniteNumber(value['sequenceIndex']) && isOptionalBoolean(value['isActiveBoundary']);
};

const isCompactionStats = (value: JsonValue | undefined): value is { count: number; tokensSaved: number } | undefined => {
    return value === undefined || (isJsonObject(value) && isFiniteNumber(value['count']) && isFiniteNumber(value['tokensSaved']));
};

const isBooleanRecord = (value: JsonValue | undefined): value is Record<string, boolean> | undefined => {
    return value === undefined || (isJsonObject(value) && Object.values(value).every((entry) => typeof entry === 'boolean'));
};

export { isAssistantTimeline, isBooleanRecord, isChatContent, isCompactionStats, isContentPreviewFeedbackState, isSoaiCompactionMarker, isToolActivityArray, isToolCallArray };
