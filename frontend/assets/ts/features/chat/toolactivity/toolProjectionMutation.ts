/* SoAI - Chat tool projection mutation helpers [frontend/assets/ts/features/chat/toolactivity/toolProjectionMutation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ChatMessage, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { TOOL_IMAGE_BASE64_FIELD, TOOL_IMAGE_BASE64_OMITTED_FIELD, TOOL_IMAGE_BASE64_TOTAL_CHARS_FIELD, resolveOmittedToolImageDescriptor, resolveToolImageDescriptor, type OmittedToolImageDescriptor, type ToolImageDescriptor } from '@features/chat/toolactivity/toolImagePayload.ts';
import { TOOL_VIDEO_BASE64_FIELD, TOOL_VIDEO_BASE64_OMITTED_FIELD, TOOL_VIDEO_BASE64_TOTAL_CHARS_FIELD, resolveOmittedToolVideoDescriptor, resolveToolVideoDescriptor, type OmittedToolVideoDescriptor, type ToolVideoDescriptor } from '@features/chat/toolactivity/toolVideoPayload.ts';
import { shouldReplaceToolProjection } from '@features/chat/toolactivity/toolProjectionFreshness.ts';

const findAssistantMessageByTimestamp = (messages: readonly ChatMessage[], assistantAtMs: number): ChatMessage | null => {
    for (const message of messages) {
        if (message.role !== 'assistant') {
            continue;
        }
        if (message.timestamp === assistantAtMs) {
            return message;
        }
    }
    return null;
};

const findToolProjectionByCallId = (message: ChatMessage, callId: string): ToolActivityItem | null => {
    if (!message.toolCallProjections) {
        return null;
    }
    return message.toolCallProjections.find((entry) => entry.callId === callId) ?? null;
};

const cloneJsonObject = (record: JsonObject): JsonObject => {
    const cloned: JsonObject = {};
    for (const [key, value] of Object.entries(record)) {
        cloned[key] = value;
    }
    return cloned;
};

interface InlineMediaDescriptorCompatibility {
    existingContentType: string;
    existingPayloadChars: number;
    existingPath: readonly string[];
    incomingContentType: string;
    incomingPath: readonly string[];
    incomingTotalChars: number | null;
}

interface ReusableInlineMediaDescriptors<TExistingDescriptor, TIncomingDescriptor> {
    existing: TExistingDescriptor;
    incoming: TIncomingDescriptor;
}

const inlineMediaDescriptorsAreCompatible = (compatibility: InlineMediaDescriptorCompatibility): boolean => {
    if (!arraysEqual(compatibility.existingPath, compatibility.incomingPath)) {
        return false;
    }
    if (compatibility.incomingContentType && compatibility.incomingContentType !== compatibility.existingContentType) {
        return false;
    }
    return compatibility.incomingTotalChars === null || compatibility.incomingTotalChars === compatibility.existingPayloadChars;
};

const resolveReusableInlineImageDescriptors = (existing: JsonValue | undefined, incoming: JsonValue | undefined, toolName: string): ReusableInlineMediaDescriptors<ToolImageDescriptor, OmittedToolImageDescriptor> | null => {
    const existingDescriptor = resolveToolImageDescriptor(existing, { toolLeafName: toolName });
    const incomingDescriptor = resolveOmittedToolImageDescriptor(incoming, { toolLeafName: toolName });
    if (existingDescriptor === null || incomingDescriptor === null) {
        return null;
    }
    if (!inlineMediaDescriptorsAreCompatible({ existingContentType: existingDescriptor.payload.contentType, existingPayloadChars: existingDescriptor.payload.imageBase64.length, existingPath: existingDescriptor.path, incomingContentType: incomingDescriptor.contentType, incomingPath: incomingDescriptor.path, incomingTotalChars: incomingDescriptor.totalChars })) {
        return null;
    }
    return { existing: existingDescriptor, incoming: incomingDescriptor };
};

const mergeInlineImageRecord = (existingRecord: JsonObject, incomingRecord: JsonObject): JsonObject => {
    const merged: JsonObject = { ...incomingRecord };
    const imageBase64 = existingRecord[TOOL_IMAGE_BASE64_FIELD];
    if (imageBase64 !== undefined) {
        merged[TOOL_IMAGE_BASE64_FIELD] = imageBase64;
    }
    if (existingRecord['content_type'] !== undefined && incomingRecord['content_type'] === undefined) {
        merged['content_type'] = existingRecord['content_type'];
    }
    if (existingRecord['size_bytes'] !== undefined) {
        merged['size_bytes'] = existingRecord['size_bytes'];
    }
    delete merged[TOOL_IMAGE_BASE64_OMITTED_FIELD];
    delete merged[TOOL_IMAGE_BASE64_TOTAL_CHARS_FIELD];
    return merged;
};

const replaceRecordAtPath = (root: JsonValue | undefined, path: readonly string[], record: JsonObject): JsonValue | undefined => {
    if (path.length === 0) {
        return record;
    }
    if (!isJsonObject(root)) {
        return root;
    }
    const [fieldName, ...remainingPath] = path;
    if (fieldName === undefined) {
        return root;
    }
    const child = root[fieldName];
    if (!isJsonObject(child)) {
        return root;
    }
    const replacement = replaceRecordAtPath(child, remainingPath, record);
    if (replacement === undefined) {
        return root;
    }
    const updatedRoot = cloneJsonObject(root);
    updatedRoot[fieldName] = replacement;
    return updatedRoot;
};

const mergeToolResultImagePayload = (existing: JsonValue | undefined, incoming: JsonValue | undefined, toolName: string): JsonValue | undefined => {
    const descriptors = resolveReusableInlineImageDescriptors(existing, incoming, toolName);
    if (descriptors === null) {
        return incoming;
    }
    const mergedRecord = mergeInlineImageRecord(descriptors.existing.record, descriptors.incoming.record);
    return replaceRecordAtPath(incoming, descriptors.incoming.path, mergedRecord);
};

const resolveReusableInlineVideoDescriptors = (existing: JsonValue | undefined, incoming: JsonValue | undefined): ReusableInlineMediaDescriptors<ToolVideoDescriptor, OmittedToolVideoDescriptor> | null => {
    const existingDescriptor = resolveToolVideoDescriptor(existing);
    const incomingDescriptor = resolveOmittedToolVideoDescriptor(incoming);
    if (existingDescriptor === null || incomingDescriptor === null) {
        return null;
    }
    if (!inlineMediaDescriptorsAreCompatible({ existingContentType: existingDescriptor.payload.contentType, existingPayloadChars: existingDescriptor.payload.videoBase64.length, existingPath: existingDescriptor.path, incomingContentType: incomingDescriptor.contentType, incomingPath: incomingDescriptor.path, incomingTotalChars: incomingDescriptor.totalChars })) {
        return null;
    }
    return { existing: existingDescriptor, incoming: incomingDescriptor };
};

const mergeInlineVideoRecord = (existingRecord: JsonObject, incomingRecord: JsonObject): JsonObject => {
    const merged: JsonObject = { ...incomingRecord };
    const videoBase64 = existingRecord[TOOL_VIDEO_BASE64_FIELD];
    if (videoBase64 !== undefined) {
        merged[TOOL_VIDEO_BASE64_FIELD] = videoBase64;
    }
    if (existingRecord['content_type'] !== undefined && incomingRecord['content_type'] === undefined) {
        merged['content_type'] = existingRecord['content_type'];
    }
    if (existingRecord['byte_size'] !== undefined) {
        merged['byte_size'] = existingRecord['byte_size'];
    }
    if (existingRecord['size_bytes'] !== undefined) {
        merged['size_bytes'] = existingRecord['size_bytes'];
    }
    delete merged[TOOL_VIDEO_BASE64_OMITTED_FIELD];
    delete merged[TOOL_VIDEO_BASE64_TOTAL_CHARS_FIELD];
    return merged;
};

const mergeToolResultVideoPayload = (existing: JsonValue | undefined, incoming: JsonValue | undefined): JsonValue | undefined => {
    const descriptors = resolveReusableInlineVideoDescriptors(existing, incoming);
    if (descriptors === null) {
        return incoming;
    }
    const mergedRecord = mergeInlineVideoRecord(descriptors.existing.record, descriptors.incoming.record);
    return replaceRecordAtPath(incoming, descriptors.incoming.path, mergedRecord);
};

const mergeToolResultMediaPayload = (existing: JsonValue | undefined, incoming: JsonValue | undefined, toolName: string): JsonValue | undefined => {
    const imageMerged = mergeToolResultImagePayload(existing, incoming, toolName);
    const merged = mergeToolResultVideoPayload(existing, imageMerged);
    if (typeof merged === 'undefined') {
        return undefined;
    }
    if (isJsonValue(merged)) {
        return merged;
    }
    throw new Error('Tool projection media merge produced a non-JSON result.');
};

const mergeHydratedToolResultIntoProjection = (target: ToolActivityItem, source: ToolActivityItem): ToolActivityItem | null => {
    const result = mergeToolResultMediaPayload(source.result, target.result, source.toolName);
    if (result === target.result) {
        return null;
    }
    const merged: ToolActivityItem = { ...target };
    if (result === undefined) {
        delete merged.result;
    } else {
        merged.result = result;
    }
    return merged;
};

const mergeToolProjectionForApplication = (existing: ToolActivityItem, incoming: ToolActivityItem): ToolActivityItem => {
    const merged: ToolActivityItem = { ...incoming };
    const mergedResult = mergeToolResultMediaPayload(existing.result, incoming.result, incoming.toolName);
    if (mergedResult !== undefined) {
        merged.result = mergedResult;
    }
    return merged;
};

const sortToolCallProjectionsBySequence = (projections: ToolActivityItem[]): void => {
    projections.sort((left, right) => left.sequenceIndex - right.sequenceIndex);
};

const upsertToolCallProjection = (message: ChatMessage, projection: ToolActivityItem): boolean => {
    if (!message.toolCallProjections) {
        message.toolCallProjections = [projection];
        return true;
    }
    const existingIndex = message.toolCallProjections.findIndex((entry) => entry.callId === projection.callId);
    if (existingIndex < 0) {
        message.toolCallProjections.push(projection);
        sortToolCallProjectionsBySequence(message.toolCallProjections);
        return true;
    }
    const existing = message.toolCallProjections[existingIndex];
    if (existing === undefined) {
        throw new Error(i18n.t('chat.agent.toolLiveInvalidPayload'));
    }
    if (!shouldReplaceToolProjection(existing, projection)) {
        const mergedHydratedMedia = mergeHydratedToolResultIntoProjection(existing, projection);
        if (mergedHydratedMedia !== null) {
            message.toolCallProjections[existingIndex] = mergedHydratedMedia;
            sortToolCallProjectionsBySequence(message.toolCallProjections);
            return true;
        }
        return false;
    }
    message.toolCallProjections[existingIndex] = mergeToolProjectionForApplication(existing, projection);
    sortToolCallProjectionsBySequence(message.toolCallProjections);
    return true;
};

export { findAssistantMessageByTimestamp, findToolProjectionByCallId, mergeHydratedToolResultIntoProjection, sortToolCallProjectionsBySequence, upsertToolCallProjection };
