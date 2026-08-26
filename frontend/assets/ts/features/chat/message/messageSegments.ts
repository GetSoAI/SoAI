/* SoAI - Chat feature message segments [frontend/assets/ts/features/chat/message/messageSegments.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { SoaiPathStoragePart } from '@features/chat/attachments/soaiPathContentPart.ts';
import type { SoaiFilePreviewType } from '@features/chat/attachments/attachmentPreviewTypes.ts';
import type { SoaiFileUnavailablePart, SoaiKnowledgeUnavailablePart } from '@features/chat/attachments/soaiUnavailableContentPart.ts';
import type { ChatContent, ChatMessage, ToolActivityCodeDiff, ToolActivityStatus } from '@features/chat/ChatTypes.ts';

interface ImageValue {
    url: string;
    detail?: string;
}

interface TextContentPart {
    type: 'text';
    text: string;
}

interface ThinkingContentPart {
    type: 'thinking';
    text: string;
}

interface ImageContentPart {
    type: 'image_url';
    imageUrl: ImageValue;
    title?: string;
    alt?: string;
}

interface ToolCallContentPart {
    type: 'tool_call';
    name?: string;
    id?: string | number;
    toolArguments?: JsonValue;
    functionArguments?: JsonValue;
    input?: JsonValue;
    parameters?: JsonValue;
    metadata?: JsonValue;
    function?: JsonObject;
}

type SoaiKnowledgeStatusCounts = Record<string, number>;

interface SoaiFileContentPart {
    type: 'soai_file';
    attachmentId: string;
    fileId: string;
    filename: string;
    mimeType: string;
    sizeBytes: number;
    previewType: SoaiFilePreviewType;
    attachmentRevision: number;
    createdAtMs: number;
}

interface SoaiKnowledgeContentPart {
    type: 'soai_knowledge';
    knowledgeAttachmentId: string;
    summaryId: string;
    sourceType: string;
    operationType: string;
    title: string;
    totalCount: number;
    visibleCount: number;
    hiddenCount: number;
    statusCounts: SoaiKnowledgeStatusCounts;
    attachmentRevision: number;
    firstEventId: number | null;
    lastEventId: number | null;
    createdAtMs: number;
    finalizedAtMs: number;
}

type SoaiFileUnavailableSegment = SoaiFileUnavailablePart;
type SoaiKnowledgeUnavailableSegment = SoaiKnowledgeUnavailablePart;

type MessageContentPart = TextContentPart | ThinkingContentPart | ImageContentPart | ToolCallContentPart | SoaiFileContentPart | SoaiKnowledgeContentPart;

type MessageContent = ChatContent | null | undefined;

interface TextSegment {
    type: 'text';
    text: string;
    value: string;
    timelineSequence?: number;
    isStreamingActive?: boolean;
    signatureSequence?: number;
}

interface ImageSegment {
    type: 'image';
    imageUrl: string;
    title: string;
    signatureSequence?: number;
    alt?: string;
    url?: string;
    src?: string;
}

interface ToolCallSegment {
    type: 'tool_call';
    name?: string;
    id?: string | number;
    toolArguments?: JsonValue;
    functionArguments?: JsonValue;
    input?: JsonValue;
    parameters?: JsonValue;
    metadata?: JsonValue;
    function?: JsonObject;
}

interface SoaiPathSegment {
    type: 'soai_path';
    title: string;
    virtualPath: string;
    rootFingerprint: string;
    entryType: string;
    contentPart: SoaiPathStoragePart;
    previewType?: string;
    mimeType?: string;
    sizeBytes?: number;
}

interface SoaiFileSegment {
    type: 'soai_file';
    attachmentId: string;
    fileId: string;
    filename: string;
    mimeType: string;
    sizeBytes: number;
    previewType: SoaiFilePreviewType;
    attachmentRevision: number;
    createdAtMs: number;
}

interface SoaiKnowledgeSegment {
    type: 'soai_knowledge';
    knowledgeAttachmentId: string;
    summaryId: string;
    sourceType: string;
    operationType: string;
    title: string;
    totalCount: number;
    visibleCount: number;
    hiddenCount: number;
    statusCounts: SoaiKnowledgeStatusCounts;
    attachmentRevision: number;
    firstEventId: number | null;
    lastEventId: number | null;
    createdAtMs: number;
    finalizedAtMs: number;
}

interface ThinkingSegment {
    type: 'thinking';
    text: string;
    value: string;
}

interface InlineToolActivitySegment {
    type: 'inline_tool_activity';
    callId: string;
    toolName: string;
    status: ToolActivityStatus;
    contentIndexBefore: number;
    assistantTurnAtMs?: number;
    modelVariantIndex?: number;
    signatureSequence?: number;
    inputArguments?: JsonValue;
    codeDiffs?: ToolActivityCodeDiff[];
    result?: JsonValue;
    error?: string;
    durationMs?: number;
    startedAtMs?: number;
    streamOrder?: number;
    collapsed: boolean;
}

interface InlineThinkingActivitySegment {
    type: 'inline_thinking_activity';
    callId: string;
    timelineSequenceIndex: number;
    contentIndexBefore: number;
    status: 'running' | 'completed' | 'cancelled' | 'error';
    text: string;
    signatureSequence?: number;
    durationMs?: number;
    startedAtMs?: number;
    collapsed: boolean;
}

interface InlineActionUpdateSegment {
    type: 'inline_action_update';
    callId: string;
    timelineSequenceIndex: number;
    contentIndexBefore: number;
    text: string;
    signatureSequence?: number;
}

interface InlineLoadingActivitySegment {
    type: 'inline_loading_activity';
    activityLifecycleKey?: string;
    status: 'running' | 'completed' | 'cancelled' | 'error';
    startedAtMs: number;
    signatureSequence?: number;
    collapsed?: boolean;
    durationMs?: number;
    reason?: string;
    errorType?: string;
}

interface InlineProcessingActivitySegment {
    type: 'inline_processing_activity';
    activityLifecycleKey?: string;
    status: 'running' | 'completed' | 'cancelled' | 'error';
    startedAtMs: number;
    signatureSequence?: number;
    collapsed?: boolean;
    durationMs?: number;
    reason?: string;
    errorType?: string;
}

interface InlineWaitForUserActivitySegment {
    type: 'inline_wait_for_user_activity';
    activityLifecycleKey?: string;
    status: 'running' | 'completed' | 'cancelled' | 'error';
    startedAtMs: number;
    signatureSequence?: number;
    collapsed?: boolean;
    durationMs?: number;
    reason?: string;
    errorType?: string;
}

type MessageSegment = TextSegment | ImageSegment | ToolCallSegment | SoaiPathSegment | SoaiFileSegment | SoaiKnowledgeSegment | SoaiFileUnavailableSegment | SoaiKnowledgeUnavailableSegment | ThinkingSegment | InlineToolActivitySegment | InlineThinkingActivitySegment | InlineActionUpdateSegment | InlineLoadingActivitySegment | InlineProcessingActivitySegment | InlineWaitForUserActivitySegment;

export type { MessageContentPart, MessageContent, MessageSegment, TextSegment, ImageSegment };
export type { ToolCallSegment, SoaiPathSegment, SoaiFileSegment, SoaiKnowledgeSegment, SoaiKnowledgeStatusCounts, ThinkingSegment, InlineToolActivitySegment };
export type { SoaiFileUnavailableSegment, SoaiKnowledgeUnavailableSegment };
export type { InlineThinkingActivitySegment, InlineActionUpdateSegment, InlineLoadingActivitySegment, InlineProcessingActivitySegment };
export type { InlineWaitForUserActivitySegment };
export type { ChatMessage };
