/* SoAI - Canonical runtime guards for chat message objects [frontend/assets/ts/features/chat/message/chatMessageGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMessageRole } from '@core/chat/messageRoles.ts';
import { isConversationMessageType } from '@core/chat/conversationMessageType.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { isAssistantTimeline, isBooleanRecord, isChatContent, isCompactionStats, isContentPreviewFeedbackState, isSoaiCompactionMarker, isToolActivityArray, isToolCallArray } from '@features/chat/message/chatMessageNestedGuards.ts';

const isFiniteNumber = (value: JsonValue | undefined): value is number => typeof value === 'number' && Number.isFinite(value);
const isOptionalFiniteNumber = (value: JsonValue | undefined): boolean => value === undefined || isFiniteNumber(value);
const isOptionalNullableFiniteNumber = (value: JsonValue | undefined): boolean => value === undefined || value === null || isFiniteNumber(value);
const isOptionalString = (value: JsonValue | undefined): boolean => value === undefined || typeof value === 'string';
const isOptionalNullableString = (value: JsonValue | undefined): boolean => value === undefined || value === null || typeof value === 'string';

const hasValidSimpleFields = (value: JsonObject): boolean => {
    const identifier = value['id'];
    return (
        (identifier === undefined || typeof identifier === 'string' || isFiniteNumber(identifier)) &&
        isOptionalFiniteNumber(value['timestamp']) &&
        isOptionalNullableFiniteNumber(value['assistantTurnAtMs']) &&
        isOptionalNullableFiniteNumber(value['modelVariantIndex']) &&
        isOptionalNullableString(value['requestId']) &&
        isOptionalNullableString(value['modelId']) &&
        isOptionalString(value['name']) &&
        isOptionalString(value['toolCallId']) &&
        isOptionalString(value['soaiConversationInputId']) &&
        isOptionalString(value['messagingSenderDisplayName']) &&
        isOptionalString(value['messagingSenderId']) &&
        (value['messageType'] === undefined || isConversationMessageType(value['messageType'])) &&
        isOptionalNullableString(value['finishReason']) &&
        isOptionalFiniteNumber(value['promptTokens']) &&
        isOptionalFiniteNumber(value['completionTokens']) &&
        isOptionalFiniteNumber(value['totalTokens']) &&
        isOptionalString(value['usageSource']) &&
        isOptionalFiniteNumber(value['generationLatencyMs']) &&
        isOptionalFiniteNumber(value['generationSpeedTokensPerSec']) &&
        isOptionalFiniteNumber(value['thinkingTailDurationMs']) &&
        isOptionalString(value['soaiMessageType']) &&
        isOptionalString(value['streamStatusPreviewText']) &&
        isOptionalFiniteNumber(value['streamStatusPreviewGeneratedAtMs']) &&
        isOptionalFiniteNumber(value['streamStatusPreviewCooldownMs']) &&
        isOptionalString(value['streamStatusPreviewTrigger']) &&
        isOptionalString(value['errorCode']) &&
        (value['assistantTimelineType'] === undefined || value['assistantTimelineType'] === 'canonical' || value['assistantTimelineType'] === 'projection')
    );
};

const hasValidJsonFields = (value: JsonObject): boolean => {
    return (value['usage'] === undefined || isJsonObject(value['usage'])) && (value['message'] === undefined || isJsonObject(value['message']));
};

const hasValidNestedFields = (value: JsonObject): boolean => {
    return isChatContent(value['content']) && isToolCallArray(value['toolCalls']) && isAssistantTimeline(value['assistantEventTimeline']) && isToolActivityArray(value['toolCallProjections']) && isContentPreviewFeedbackState(value['contentPreviewFeedbackState']) && isSoaiCompactionMarker(value['soaiCompaction']) && isCompactionStats(value['soaiCompactionStats']) && isBooleanRecord(value['inlineThinkingCollapsedByCallId']) && isBooleanRecord(value['inlineToolCollapsedByCallId']);
};

const isChatMessage = <T>(value: T): value is T & ChatMessage => {
    if (!isJsonObject(value) || typeof value['role'] !== 'string' || !isMessageRole(value['role'])) {
        return false;
    }
    return hasValidSimpleFields(value) && hasValidJsonFields(value) && hasValidNestedFields(value);
};

const assertKnownChatMessageFields = (value: JsonObject, context: string): void => {
    for (const fieldName of Object.keys(value)) {
        switch (fieldName) {
            case 'id':
            case 'role':
            case 'content':
            case 'timestamp':
            case 'assistantTurnAtMs':
            case 'modelVariantIndex':
            case 'requestId':
            case 'modelId':
            case 'name':
            case 'toolCallId':
            case 'soaiConversationInputId':
            case 'messagingSenderDisplayName':
            case 'messagingSenderId':
            case 'messageType':
            case 'toolCalls':
            case 'finishReason':
            case 'promptTokens':
            case 'completionTokens':
            case 'totalTokens':
            case 'usageSource':
            case 'generationLatencyMs':
            case 'generationSpeedTokensPerSec':
            case 'thinkingTailDurationMs':
            case 'assistantEventTimeline':
            case 'assistantTimelineType':
            case 'toolCallProjections':
            case 'contentPreviewFeedbackState':
            case 'soaiMessageType':
            case 'soaiCompaction':
            case 'soaiCompactionStats':
            case 'streamStatusPreviewText':
            case 'streamStatusPreviewGeneratedAtMs':
            case 'streamStatusPreviewCooldownMs':
            case 'streamStatusPreviewTrigger':
            case 'inlineThinkingCollapsedByCallId':
            case 'inlineToolCollapsedByCallId':
            case 'errorCode':
            case 'usage':
            case 'attachments':
            case 'images':
            case 'documents':
            case 'message':
                break;
            default:
                throw new Error(`${context} contains unsupported field '${fieldName}'`);
        }
    }
};

const decodeChatMessage = (value: JsonValue | null | undefined, context: string): ChatMessage => {
    if (!isJsonObject(value)) {
        throw new Error(`${context} must be a JSON object`);
    }
    assertKnownChatMessageFields(value, context);
    if (!isChatMessage(value)) {
        throw new Error(`${context} contains invalid chat message fields`);
    }
    return value;
};

export { decodeChatMessage, isChatMessage };
