/* SoAI - Chat feature worker request decoding [frontend/assets/ts/features/chat/messagerenderworker/workerRequestDecoding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import { assertNonEmptyString, requireBooleanValue, requireFiniteNumber, requirePlainObject } from '@core/assertions.ts';
import { isClockFormatPreference, isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/localization/public.ts';
import { type JsonObject, type JsonValue, isJsonObject } from '@core/types/jsonValues.ts';
import { isPlainObject, isString } from '@core/typeGuards.ts';
import { isStringRecordValue } from '@core/types/runtimeCollectionGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { decodeChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import type { InitializeResourcesRequest, RenderAssistantBodyFromMessageRequest, RenderContext, RenderInlineDetailsFromMessageRequest, RenderMessageCommonFields, WorkerRequest, WorkerResources } from '@features/chat/messagerenderworker/protocol.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';

type DecodedWorkerRequest = WorkerRequest;

const requireBoolean = (value: JsonValue | null | undefined, context: string): boolean => requireBooleanValue(value, context, { message: `${context} must be boolean` });

const requireNumber = (value: JsonValue | null | undefined, context: string): number => requireFiniteNumber(value, context, { message: `${context} must be a finite number` });

const requireString = (value: JsonValue | null | undefined, context: string): string => assertNonEmptyString(value, context, { message: `${context} must be a non-empty string` });

const requireActivityDurationDisplayMode = (value: JsonValue | null | undefined, context: string): ChatActivityDurationDisplayMode => {
    const displayMode = requireString(value, context);
    if (displayMode !== 'all' && displayMode !== 'expandedOnly') {
        throw new Error(`${context} must be all or expandedOnly`);
    }
    return displayMode;
};

const requirePlainRecord = (value: JsonValue | null | undefined, context: string): JsonObject => {
    requirePlainObject(value, context, { message: `${context} must be a plain object` });
    if (!isJsonObject(value)) {
        throw new Error(`${context} must be a JSON object`);
    }
    return value;
};

const requireNullableNonNegativeInteger = (value: JsonValue | null | undefined, context: string): number | null => {
    if (value === null) {
        return null;
    }
    const numberValue = requireNumber(value, context);
    if (!Number.isInteger(numberValue) || numberValue < 0) {
        throw new Error(`${context} must be a non-negative integer or null`);
    }
    return Math.floor(numberValue);
};

const isLocalizationSnapshot = (value: JsonValue | undefined): boolean => {
    if (!isJsonObject(value) || !isJsonObject(value['preferences'])) {
        return false;
    }
    const preferences = value['preferences'];
    return typeof preferences['language'] === 'string' && isClockFormatPreference(preferences['clockFormat']) && isRegionalLocalePreference(preferences['regionalLocale']) && isDateFormatPreference(preferences['dateFormat']) && isMeasurementUnitsPreference(preferences['measurementUnits']) && typeof value['locale'] === 'string' && (value['dateOrder'] === 'locale' || value['dateOrder'] === 'us' || value['dateOrder'] === 'eu' || value['dateOrder'] === 'iso') && (value['measurementUnits'] === 'metric' || value['measurementUnits'] === 'imperial') && typeof value['hour12'] === 'boolean' && typeof value['version'] === 'number' && Number.isFinite(value['version']);
};

const isWorkerResources = <T>(value: T | string | number | boolean | null | undefined): value is T & WorkerResources => {
    if (!isJsonObject(value)) {
        return false;
    }
    return isStringRecordValue(value['translationsByKey']) && isStringRecordValue(value['iconsByKey']) && isLocalizationSnapshot(value['localizationSnapshot']);
};

const decodeCanonicalPlan = (value: JsonValue | null | undefined): AgentCanonicalPlan | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const markdown = value['markdown'];
    if (typeof markdown !== 'string' || !markdown.trim()) {
        return null;
    }
    const title = value['title'];
    const revision = value['revision'];
    return {
        markdown,
        title: typeof title === 'string' && title.trim() ? title : null,
        revision: typeof revision === 'number' && Number.isInteger(revision) ? revision : null
    };
};

const requireChatMessage = (value: JsonValue | null | undefined, context: string): ChatMessage => {
    const message = decodeChatMessage(value, context);
    if (message.role !== 'assistant') {
        throw new Error(`${context}.role must be assistant`);
    }
    return message;
};

const requireRenderContext = (value: JsonValue | null | undefined, context: string): RenderContext => {
    const record = requirePlainRecord(value, context);
    const epoch = requireNumber(record['epoch'], `${context}.epoch`);
    const conversationId = requireString(record['conversationId'], `${context}.conversationId`);
    const messageDomId = requireString(record['messageDomId'], `${context}.messageDomId`);
    const messageRevision = requireNumber(record['messageRevision'], `${context}.messageRevision`);
    const stateSignature = requireString(record['stateSignature'], `${context}.stateSignature`);
    return {
        epoch: Math.floor(epoch),
        conversationId,
        messageDomId,
        messageRevision: Math.floor(messageRevision),
        stateSignature
    };
};

const decodeInitializeResourcesRequest = (request: JsonObject, requestId: string): InitializeResourcesRequest => {
    const context = 'Chat render worker initResources';
    if (!('resources' in request) || !isPlainObject(request['resources'])) {
        throw new Error(`${context} missing resources`);
    }
    if (!isWorkerResources(request['resources'])) {
        throw new Error(`${context} invalid resources`);
    }
    return { type: 'initResources', requestId, resources: request['resources'] };
};

const decodeRenderMessageRequestFields = (request: JsonObject, context: string): Omit<RenderMessageCommonFields, 'nowMs' | 'message'> => {
    const renderContext = requireRenderContext(request['context'], `${context}.context`);
    const isRichTextEnabled = requireBoolean(request['isRichTextEnabled'], `${context}.isRichTextEnabled`);
    const codeRecognitionEnabled = requireBoolean(request['codeRecognitionEnabled'], `${context}.codeRecognitionEnabled`);
    const isThinkingFeatureEnabled = requireBoolean(request['isThinkingFeatureEnabled'], `${context}.isThinkingFeatureEnabled`);
    const isShowActivitiesEnabled = requireBoolean(request['isShowActivitiesEnabled'], `${context}.isShowActivitiesEnabled`);
    const activityDurationDisplayMode = requireActivityDurationDisplayMode(request['activityDurationDisplayMode'], `${context}.activityDurationDisplayMode`);
    const isCurrentConversationExecuting = requireBoolean(request['isCurrentConversationExecuting'], `${context}.isCurrentConversationExecuting`);
    const canonicalPlan = decodeCanonicalPlan(request['canonicalPlan']);
    return {
        context: renderContext,
        isRichTextEnabled,
        codeRecognitionEnabled,
        isThinkingFeatureEnabled,
        isShowActivitiesEnabled,
        activityDurationDisplayMode,
        isCurrentConversationExecuting,
        canonicalPlan
    };
};

const decodeRenderAssistantBodyRequest = (request: JsonObject, requestId: string): RenderAssistantBodyFromMessageRequest => {
    const context = 'Chat render worker renderAssistantBodyFromMessage';
    const fields = decodeRenderMessageRequestFields(request, context);
    const suppressAssistantActivityWidgets = requireBoolean(request['suppressAssistantActivityWidgets'], `${context}.suppressAssistantActivityWidgets`);
    const nowMs = Math.floor(requireNumber(request['nowMs'], `${context}.nowMs`));
    const message = requireChatMessage(request['message'], `${context}.message`);
    return {
        type: 'renderAssistantBodyFromMessage',
        requestId,
        ...fields,
        suppressAssistantActivityWidgets,
        nowMs,
        message
    };
};

const decodeRenderInlineDetailsRequest = (request: JsonObject, requestId: string): RenderInlineDetailsFromMessageRequest => {
    const context = 'Chat render worker renderInlineDetailsFromMessage';
    const fields = decodeRenderMessageRequestFields(request, context);
    const nowMs = Math.floor(requireNumber(request['nowMs'], `${context}.nowMs`));
    const expectedType = requireString(request['expectedType'], `${context}.expectedType`);
    if (expectedType !== 'inline_tool_activity' && expectedType !== 'inline_thinking_activity') {
        throw new Error(`${context}.expectedType must be inline_tool_activity or inline_thinking_activity`);
    }
    const callId = requireString(request['callId'], `${context}.callId`);
    if (!('timelineSequenceIndex' in request)) {
        throw new Error(`${context}.timelineSequenceIndex is required`);
    }
    const timelineSequenceIndex = requireNullableNonNegativeInteger(request['timelineSequenceIndex'], `${context}.timelineSequenceIndex`);
    const message = requireChatMessage(request['message'], `${context}.message`);
    return {
        type: 'renderInlineDetailsFromMessage',
        requestId,
        ...fields,
        nowMs,
        expectedType,
        callId,
        timelineSequenceIndex,
        message
    };
};

const decodeWorkerRequest = (request: JsonValue | null | undefined): DecodedWorkerRequest => {
    if (!isPlainObject(request)) {
        throw new Error('Chat render worker received an invalid request');
    }
    const typeValue = request['type'];
    const requestIdValue = request['requestId'];
    if (!isString(typeValue) || !typeValue.trim() || !isString(requestIdValue) || !requestIdValue.trim()) {
        throw new Error('Chat render worker received an invalid request');
    }
    const type = typeValue.trim();
    const requestId = requestIdValue.trim();

    if (type === 'initResources') {
        return decodeInitializeResourcesRequest(request, requestId);
    }
    if (type === 'renderAssistantBodyFromMessage') {
        return decodeRenderAssistantBodyRequest(request, requestId);
    }
    if (type === 'renderInlineDetailsFromMessage') {
        return decodeRenderInlineDetailsRequest(request, requestId);
    }
    throw new Error('Chat render worker received an unknown request type');
};

export { decodeWorkerRequest };
export type { DecodedWorkerRequest };
